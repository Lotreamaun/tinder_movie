"""
Конфигурация приложения Movie Tinder Bot
"""
import os
from typing import Optional
from dotenv import load_dotenv

"""
Обращается к .env и загружает их в системные переменные окружения ДО создания settings.
Без этого os.getenv() не увидит их из .env.
"""
load_dotenv()

class Settings:
    """
    Настройки приложения:
    Все свойства класса закружаются из .env и имеют значения по умолчанию,
    которые будут использоваться, если переменная окружения не задана.
    """
    
    # База данных
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/tinder_movie")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Kinopoisk API
    KINOPOISK_API_KEY: str = os.getenv("KINOPOISK_API_KEY", "")
    KINOPOISK_BASE_URL: str = os.getenv("KINOPOISK_BASE_URL", "https://kinopoiskapiunofficial.tech")
    
    # Приложение
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("PORT", "8000"))
    APP_DEBUG: bool = os.getenv("APP_ENV", "development") == "development"
    
    # CORS / Frontend
    """
    Указывается разрешенные домены для CORS. 
    В проде нужно указать реальный домен, а не localhost.
    """
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    
    # Безопасность
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    
    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")
    
    # Бизнес-логика
    MAX_ROOM_SIZE: int = 5
    SESSION_DURATION_HOURS: int = 24 * 30  # 30 дней
    MOVIE_CACHE_TTL: int = 3600  # 1 час
    MIN_MOVIES_COUNT: int = 50  # Минимальное количество фильмов в БД
    MOVIES_LOAD_THRESHOLD: int = 20  # Порог для загрузки новых фильмов
    MOVIES_LOAD_BATCH: int = 30  # Количество фильмов для загрузки за раз
    MAX_MOVIES_IN_DB: int = 100  # Максимальное количество фильмов в БД (ротация)

# Создаем экземпляр настроек
settings = Settings()