import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SwipeType(str, enum.Enum):
    like = "like"
    dislike = "dislike"


class UserSwipe(Base):
    __tablename__ = "user_swipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    swipe_type = Column(Enum(SwipeType, name="swipe_type"), nullable=False)
    swiped_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    group_participants = Column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", "group_participants", name="uq_swipe_user_movie_group"),
        Index("idx_user_swipes_user_id", "user_id"),
    )


