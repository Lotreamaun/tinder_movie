import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    matched_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    is_notified = Column(Boolean, default=False, nullable=False)
    group_participants = Column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("movie_id", "group_participants", name="uq_match_movie_group"),
        Index("idx_matches_group_participants", "group_participants", postgresql_using="gin"),
    )


