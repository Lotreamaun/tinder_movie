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

from app.database import Base  # Общий родительский класс, от него наследуются все модели


class Match(Base):
    __tablename__ = "matches"  # Принудительное указание имени в PostgreSQL

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        # Column: создание столбца в таблице
        # UUID(as_uuid=True): тип данных в PostgreSQL — родной формат, а Python просим отдавать объект uuid
        # primary_key=True: уникальный ключ, по которому БД будет отличать один мэтч от другого
        # default=uuid.uuid4: если не указать id, Python вызовет функции и создаст его автоматически
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
        # Column, UUID — то же самое
        # ForeignKey("movies.id", ondelete="CASCADE"): ссылка на поле id в таблице movies
        # ondelete="CASCADE": если удалить фильм из БД, удалиться и мэтч, связанный с ним
        # nullable=False: запрещает оставлять этот столбец пустым
    matched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
        # DateTime(timezone=True): тип данных, который хранит дату и время, обычно UTC+0
        # default=lambda: datetime.now(timezone.utc): передает не время, а функцию, которая вернет время создания мэтча
        # если убрать lambda, то во всех строчках будет время запуска сервера, а не создания мэтча
    is_notified = Column(Boolean, default=False, nullable=False)
        # Boolean: тип данных True/False
        # default=False: по умолчанию, когда мэтч только случился, уведомление еще не отправлено, поэтому False
    group_participants = Column(JSON, nullable=False)
        # JSON: тип данных, который хранит список/массив в БД, в нашем случае это список telegram_id участников группы
    
    # Настройка правил для таблицы
    __table_args__ = (
        # Защита от дублирования мэтчей: если фильм и список участников уже есть в БД, не создавать новый мэтч
        # name="uq_match_movie_group" — имя этого правила в БД
        UniqueConstraint("movie_id", "group_participants", name="uq_match_movie_group"),
        Index("idx_matches_group_participants", "group_participants", postgresql_using="gin"),
    )
