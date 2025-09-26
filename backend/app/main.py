"""
Точка входа для Movie Tinder Bot
"""
import os
from dotenv import load_dotenv
from app.bot.handlers import run_polling

from app.config import settings
from app.logging_config import setup_logging
from fastapi import FastAPI
from .api.users import router as users_router
from .api.swipes import router as swipes_router
from .api.movies import router as movies_router
from .api.matches import router as matches_router
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="Movie Tinder API", debug=settings.APP_DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(swipes_router)
app.include_router(movies_router)
app.include_router(matches_router)

@app.get("/")
def read_root():
    return {
        "message": "Hello from FastAPI",
        "docs": "/docs"
        }

@app.get("/health")
def health_check():
    return {"status": "ok"}


def main():
    """Основная функция запуска приложения"""
    # Загружаем переменные окружения
    load_dotenv()
    
    # Настраиваем логирование
    logger = setup_logging(settings.LOG_LEVEL, settings.LOG_FILE)
    
    logger.info("=" * 50)
    logger.info("Movie Tinder Bot - Запуск приложения")
    logger.info("=" * 50)
    logger.info(f"Режим: {'development' if settings.APP_DEBUG else 'production'}")
    logger.info(f"Хост: {settings.APP_HOST}:{settings.APP_PORT}")
    logger.info(f"База данных: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'не настроена'}")
    logger.info(f"Redis: {settings.REDIS_URL}")
    logger.info(f"Telegram Bot Token: {'настроен' if settings.TELEGRAM_BOT_TOKEN else 'НЕ НАСТРОЕН'}")
    logger.info("=" * 50)
    
    print("Приложение запущено")
    logger.info("Приложение успешно запущено")

    # Опциональный запуск Telegram-бота по флагу окружения
    if os.getenv("RUN_BOT") == "1":
        run_polling()


if __name__ == "__main__":
    main()