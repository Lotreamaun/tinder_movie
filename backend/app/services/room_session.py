"""Сессия комнаты — скользящее окно активности группы участников.

Сессия продолжается, пока между соседними свайпами любых участников группы
проходит меньше `ROOM_SESSION_GAP_HOURS`. Если с последнего свайпа группы
прошло больше — сессия пуста: прошлые свайпы не исключают фильмы из показа и
не участвуют в проверке матча (design.md, Decision 5). Вычисляется на лету по
`user_swipes`, без хранимого состояния.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import logger
from app.models.swipe import UserSwipe


def get_session_start(
    db: Session,
    participants: list[int],
    room_code: Optional[str] = None,
) -> Optional[datetime]:
    """Начало текущей сессии группы участников.

    Args:
        db: Сессия БД.
        participants: telegram_id участников группы (сопоставление через `@>`).
        room_code: Код комнаты — только для контекста в логах.

    Returns:
        Момент первого свайпа текущей непрерывной серии, либо None, если
        свайпов группы нет или с последнего прошло не меньше порога простоя
        (сессия пуста).
    """
    gap = timedelta(hours=settings.ROOM_SESSION_GAP_HOURS)
    group_swipes = (
        select(
            UserSwipe.swiped_at.label("swiped_at"),
            func.lag(UserSwipe.swiped_at).over(order_by=UserSwipe.swiped_at).label("prev_swiped_at"),
        )
        .where(cast(UserSwipe.group_participants, JSONB).op("@>")(participants))
        .subquery()
    )
    last_swiped_at, session_start = db.execute(
        select(
            func.max(group_swipes.c.swiped_at),
            func.max(group_swipes.c.swiped_at).filter(
                or_(
                    group_swipes.c.prev_swiped_at.is_(None),
                    group_swipes.c.swiped_at - group_swipes.c.prev_swiped_at >= gap,
                )
            ),
        )
    ).one()

    if last_swiped_at is None:
        return None

    idle = datetime.now(timezone.utc) - last_swiped_at
    if idle >= gap:
        logger.info(
            "Room session expired room=%s participants=%s idle=%s", room_code, participants, idle
        )
        return None
    return session_start
