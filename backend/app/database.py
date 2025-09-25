"""
SQLAlchemy sync setup for Movie Tinder Bot
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings


# Engine and Session factory (sync)
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
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


