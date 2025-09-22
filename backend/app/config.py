"""
Конфигурация приложения Movie Tinder Bot
"""
import os
from typing import Optional


class Settings:
    """Настройки приложения"""
    
    # База данных
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/tinder_movie")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Kinopoisk API
    KINOPOISK_API_KEY: str = os.getenv("KINOPOISK_API_KEY", "")
    KINOPOISK_BASE_URL: str = os.getenv("KINOPOISK_BASE_URL", "https://kinopoiskapiunofficial.tech/api")
    
    # Приложение
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    APP_DEBUG: bool = os.getenv("APP_ENV", "development") == "development"
    
    # CORS / Frontend
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    
    # Безопасность
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    
    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")
    
    # Бизнес-логика
    MAX_GROUP_SIZE: int = 5
    SESSION_DURATION_HOURS: int = 24 * 30  # 30 дней
    MOVIE_CACHE_TTL: int = 3600  # 1 час


# Создаем экземпляр настроек
settings = Settings()
