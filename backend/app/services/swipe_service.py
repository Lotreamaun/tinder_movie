from typing import Optional, Sequence

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.swipe import SwipeType, UserSwipe

class SwipeService:
    def create_swipe(
        self,
        db: Session,
        user_id: str,
        movie_id: str,
        swipe_type: SwipeType,
        group_participants: list[int],
    ) -> UserSwipe:
        swipe = UserSwipe(
            user_id=user_id,
            movie_id=movie_id,
            swipe_type=swipe_type,
            group_participants=group_participants,
        )
        db.add(swipe)
        db.commit()
        db.refresh(swipe)
        return swipe


    def list_user_swipes(self, db: Session, user_id: str, limit: int = 50, offset: int = 0) -> Sequence[UserSwipe]:
        stmt = select(UserSwipe).where(UserSwipe.user_id == user_id).order_by(UserSwipe.swiped_at.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars())


    def get_swipe(self, db: Session, user_id: str, movie_id: str, group_participants: list[int]) -> Optional[UserSwipe]:
        stmt = select(UserSwipe).where(
            and_(
                UserSwipe.user_id == user_id,
                UserSwipe.movie_id == movie_id,
                UserSwipe.group_participants == group_participants,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def check_match(self, db: Session, movie_id: str, group_participants: list[int]) -> bool:
        """
        Проверяет, поставили ли все участники группы лайк фильму.
        
        Args:
            db (Session): Сессия БД
            movie_id (str): ID фильма
            group_participants (list[int]): Список telegram_id участников группы
            
        Returns:
            bool: True если все участники лайкнули фильм, False иначе
        """
        stmt = select(UserSwipe).where(
            and_(
                UserSwipe.movie_id == movie_id,
                UserSwipe.swipe_type == 'like',
                UserSwipe.group_participants == group_participants
            )
        )
        likes = db.execute(stmt).scalars().all()
        
        # Считаем уникальных пользователей, поставивших лайк
        unique_users = set(like.user_id for like in likes)
        
        # Матч, если количество уникальных лайков равно количеству участников
        return len(unique_users) == len(group_participants)

swipe_service = SwipeService()