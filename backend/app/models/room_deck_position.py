"""Модель позиции участника в общем упорядоченном колоде фильмов комнаты."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class RoomDeckPosition(Base):
    """Курсор участника в общем колоде комнаты.

    position — индекс в movie_ids колода (room_decks.movie_ids), с которого
    участнику будет выдан следующий фильм. Каждый запрос «следующего фильма»
    продвигает позицию вперёд, поэтому повторные/параллельные запросы
    возвращают разные фильмы без повторов для участника.
    """
    __tablename__ = "room_deck_positions"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    room_code = Column(
        String, ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
    )
    position = Column(Integer, nullable=False, default=0)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
