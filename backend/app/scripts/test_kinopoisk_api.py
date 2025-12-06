"""
Простой скрипт для проверки работы Kinopoisk API.

Использование:
    python -m app.scripts.test_kinopoisk_api [kinopoisk_id]

Примеры:
    python -m app.scripts.test_kinopoisk_api 301        # Матрица
    python -m app.scripts.test_kinopoisk_api 435        # Зеленая миля
    python -m app.scripts.test_kinopoisk_api 435       # Побег из Шоушенка
"""
import sys
from app.services.movie_service import movie_service
from app.config import settings
from app.logging_config import logger


def test_kinopoisk_api(kinopoisk_id: int) -> None:
    """
    Тестирует получение данных фильма из Kinopoisk API.
    
    Args:
        kinopoisk_id: ID фильма в Kinopoisk
    """
    print("=" * 60)
    print(f"Тестирование Kinopoisk API для фильма ID: {kinopoisk_id}")
    print("=" * 60)
    
    # Проверяем наличие API ключа
    if not settings.KINOPOISK_API_KEY:
        print("❌ ОШИБКА: KINOPOISK_API_KEY не задан в переменных окружения")
        print("   Установите ключ в .env файле: KINOPOISK_API_KEY=your_key")
        return
    
    print(f"✅ API ключ найден")
    print(f"   Base URL: {settings.KINOPOISK_BASE_URL}")
    print(f"   Full URL будет: {settings.KINOPOISK_BASE_URL}/films/{kinopoisk_id}")
    print()
    
    # Получаем данные из API
    print(f"Запрос данных для фильма {kinopoisk_id}...")
    print(f"   URL: {settings.KINOPOISK_BASE_URL}/films/{kinopoisk_id}")
    print()
    data = movie_service.fetch_movie_from_kinopoisk(kinopoisk_id)
    
    if not data:
        print("❌ Не удалось получить данные из API")
        print("   Возможные причины:")
        print("   - Неверный kinopoisk_id")
        print("   - Проблемы с API ключом")
        print("   - Проблемы с сетью")
        return
    
    print("✅ Данные успешно получены!")
    print()
    print("Полученные данные:")
    print("-" * 60)
    
    if data.get("poster_url"):
        print(f"📸 Постер: {data['poster_url']}")
    else:
        print("📸 Постер: не найден")
    
    if data.get("title_original"):
        print(f"🎬 Оригинальное название: {data['title_original']}")
    else:
        print("🎬 Оригинальное название: не найдено")
    
    if data.get("rating") is not None:
        print(f"⭐ Рейтинг: {data['rating']}")
    else:
        print("⭐ Рейтинг: не найден")
    
    if data.get("description"):
        desc = data['description'][:100] + "..." if len(data['description']) > 100 else data['description']
        print(f"📝 Описание: {desc}")
    else:
        print("📝 Описание: не найдено")
    
    print("-" * 60)
    print("✅ API работает корректно!")


if __name__ == "__main__":
    # Получаем kinopoisk_id из аргументов командной строки или используем тестовый
    if len(sys.argv) > 1:
        try:
            kinopoisk_id = int(sys.argv[1])
        except ValueError:
            print("❌ Ошибка: kinopoisk_id должен быть числом")
            print(f"   Использование: python -m app.scripts.test_kinopoisk_api [kinopoisk_id]")
            sys.exit(1)
    else:
        # Тестовый ID - Матрица (1999)
        kinopoisk_id = 301
        print("ℹ️  Используется тестовый kinopoisk_id (301 - Матрица)")
        print("   Для другого фильма укажите ID: python -m app.scripts.test_kinopoisk_api [id]")
        print()
    
    test_kinopoisk_api(kinopoisk_id)

