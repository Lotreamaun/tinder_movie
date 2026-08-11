"""Модель общего упорядоченного колода фильмов комнаты."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class RoomDeck(Base):
    """Общий упорядоченный колод фильмов комнаты.

    movie_ids — упорядоченный массив строковых UUID фильмов (JSONB).
    Позиция участника не хранится: «следующий фильм» вычисляется как первый
    id колода, который ещё не свайпнут участником в этой комнате.
    """
    __tablename__ = "room_decks"

    room_code = Column(
        String, ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
    )
    movie_ids = Column(JSONB, nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
