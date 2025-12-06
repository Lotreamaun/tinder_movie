import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON, ForeignKey

from app.database import Base


class Room(Base):
    __tablename__ = "rooms"

    id = Column(String, primary_key=True)  # Уникальный код комнаты (например, "ABC123")
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    participants = Column(JSON, nullable=False, default=list)  # Список telegram_id участников
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_rooms_creator_id", "creator_id"),
        Index("idx_rooms_created_at", "created_at"),
    )
