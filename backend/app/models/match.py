"""Модель для мэтча – ситуации, когда все участники лайкнули фильм"""
import uuid  # Генерация уникальных id для записи в таблице
from datetime import datetime, timezone  # Время по Гринвичу (всемирное координированное время)

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, UniqueConstraint
    # JSON - колонка типа список/массив в БД
    # Boolean – поле True/False
    # Column - класс для определения столбцов (полей) в таблице
    # DateTime - дата и время
    # ForeignKey - класс для создания внешнего ключа, который может связывать таблицы между собой
        # напр. есть таблицы cars и humans
        # В таблице humans у каждого человека есть id, в таблице cars есть поле owner_id
        # вот в owner_id в качестве аргумента укажем (ForeignKey(humans.id))
        # Таким образом мы привяжем реальный id из humans к таблице Cars
    # Index - структура данных для поисках по индексам, ускоряет поиск по БД (упрощено)
    # UniqueConstraint - класс для ограничения уникальности
        # чтобы в таблице пара полей не могли повториться в одной строчке
        # напр., в нашем случае в одном мэтче не можем быть двух одинаковых 
        # movie_id (фильма) и group_participants (списка участников)
from sqlalchemy.dialects.postgresql import UUID  # Тип данных в PostgreSQL 

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
