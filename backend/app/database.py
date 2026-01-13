"""
Настройка SQLAlchemy в синхронном (последовательные операции) режиме
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

"""
Create_engine(): создает подключение к БД, внутри объекта engine хранятся параметры доступа к БД (URL и тд)

Args:
    settings.DATABASE_URL — подтягивает URL из файла конфигурации
    pool_pre_ping=True — проверка соединения перед использованием (важно для прода)
    future=True - включает интерфейс API SQAlchemy 2.0

Engine создается только один раз — при запуске приложения
"""
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)

"""
Sessionmaker - фабрика для создания сессий БД
"""
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# Base class for ORM models
Base = declarative_base()


def get_db():
    """Yield a new database session and ensure proper close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()