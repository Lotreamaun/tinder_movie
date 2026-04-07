import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class User(Base):
    """Пользователь телеграм-бота.

    last_active — время последней активности, используется для отслеживания
    активных пользователей.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    last_active = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
