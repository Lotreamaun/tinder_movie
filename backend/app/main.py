"""
Точка входа для Movie Tinder Bot
"""

# TODO: Написать коммент к каждому блоку кода (см. #1 в issue)

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

app = FastAPI(
    title="Movie Tinder API",
    debug=settings.APP_DEBUG)


"""
CORS middleware — это механизм безопасности
Он позволяет указать, какие домены могут делать запросы к API
API примет запрос и обработает его в любом случае,
но браузер заблокирует ответ и не передаст домену, если он не в списке allow_origins
"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

"""
Метод .include_router() подключает маршруты (эндпоинты) из других модулей приложения

Основные параметры:
    prefix: добавляет префикс к URL-адресу эндпоинта, напр. prefix="/api" превратит путь /users в /api/users;
    tags: добавляет тег к эндпоинту, чтобы можно было группировать эндпоинты в Swagger UI;
    dependencies: добавляет зависимости к эндпоинту, чтобы можно было использовать в эндпоинте,
    например, можно написать функцию, которая будет проверять текст заголовка и указать ее в качестве аругмента
    через Depends();
    responses: добавляет ответы к эндпоинту, чтобы можно было описать возможные ошибки и их коды,
    например, responses={404: {"description": "Пользователь не найден"}}. Можно задать ответы по умолчанию 
    для всех эндпоинтов роутера. Это удобно, чтобы не дублировать однотипные ошибки 
    (например, 401 — “Unauthorized”) для группы маршрутов сразу.
"""
app.include_router(users_router)
app.include_router(swipes_router)
app.include_router(movies_router)
app.include_router(matches_router)


"""
@app.get("/") — это декоратор FastAPI (декоратор в Python — это "обертка" вокруг функции)
Технически — это функция, которая принимает другую функцию и возвращает новую функцию с расширенной логикой.
Когда пишем @что-то над функцией, это значит «взять функцию ниже и пропустить ее через декоратор `что-то`»
Конкретно @app.get("/") регистрирует функцию read_root() как обработчик HTTP-запроса метода GET пути / (корень)
Короче функция read_root() будет вызываться, когда кто-то запросит корень сайта.
"""
@app.get("/")
def read_root():
    return {
        "message": "Hello from FastAPI",
        "docs": "/docs"
        }

"""
Эндпоинт для проверки работоспособности сервера
При обращении GET /health будет возвращаться JSON с сообщением "status": "ok"
"""
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

    """
    run_polling() — это функция, которая фактически запускает Telegram-бот.
    Опциональный запуск нужен, чтобы не запускать бота, если он не настроен
    или чтобы можно было отдельно запускать бота и API
    """
    # Опциональный запуск Telegram-бота по флагу окружения
    if os.getenv("RUN_BOT") == "1":
        run_polling()

"""
Это защита от случайного запуска скрипта при импорте модуля:
если мы напишем import main, то скрипт не запустится.
Для запуска нужно явно указать python3 main.py
"""
if __name__ == "__main__":
    main()