"""Точка входа для запуска только Telegram-бота"""
import os
import logging
from dotenv import load_dotenv

# Импортируем настройки и функцию запуска бота
from app.config import settings
from app.logging_config import setup_logging
from app.bot.handlers import run_polling

def main():
    """Запускает Telegram-бота Movie Tinder"""
    load_dotenv()  # Загружаем переменные окружения из .env
    
    logger = setup_logging(settings.LOG_LEVEL, settings.LOG_FILE)  # Берем настройки логирования из конфига
    
    logger.info("=" * 50)
    logger.info("MOVIE TINDER BOT - ЗАПУСК ПРОЦЕССА БОТА")
    logger.info("=" * 50)
    
    # Проверка критических настроек перед стартом
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("Критическая ошибка: TELEGRAM_BOT_TOKEN не найден!")
        return

    try:
        logger.info("Бот начинает опрос серверов (polling)...")
        # 3. Запускаем бесконечный цикл бота
        run_polling()
    except Exception as e:
        logger.exception(f"Бот упал с ошибкой: {e}")

if __name__ == "__main__":
    main()