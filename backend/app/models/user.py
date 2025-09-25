import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    last_active = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        # Partial index analogue via SQLAlchemy is limited; Alembic will create functional/where if needed
        Index("idx_users_active", "last_active"),
    )


