import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Movie(Base):
    __tablename__ = "movies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kinopoisk_id = Column(Integer, unique=True, nullable=False)
    title = Column(String, nullable=False)
    title_original = Column(String, nullable=True)
    year = Column(Integer, nullable=False)
    genre = Column(String, nullable=False)
    poster_url = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    rating = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_movies_kinopoisk_id", "kinopoisk_id"),
    )


