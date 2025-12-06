"""
Скрипт для обновления СУЩЕСТВУЮЩИХ фильмов в БД данными из Kinopoisk API.
Если нечего обновлять - добавляет 5 новых популярных фильмов.

Использование:
    python -m app.scripts.update_movies_from_kinopoisk

Скрипт:
1. Обновляет все фильмы в БД, у которых нет постеров (или постер не начинается с "http")
2. Если нечего обновлять - добавляет 5 новых популярных фильмов из Kinopoisk API
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.movie_service import movie_service
from app.logging_config import logger


def update_movies() -> None:
    """
    Обновляет данные фильмов из Kinopoisk API.
    Обновляет только фильмы без постеров или с пустыми данными.
    """
    db = SessionLocal()
    try:
        # Получаем все фильмы
        movies = movie_service.list_movies(db, limit=1000)
        logger.info(f"Found {len(movies)} movies to check")
        
        updated = 0
        skipped = 0
        failed = 0
        
        for movie in movies:
            # Пропускаем если уже есть валидный постер (начинается с http)
            if movie.poster_url and movie.poster_url.startswith("http"):
                skipped += 1
                continue
            
            logger.info(f"Updating movie {movie.kinopoisk_id}: {movie.title}")
            
            # Получаем данные из API (только для обновления)
            data = movie_service.fetch_movie_from_kinopoisk(movie.kinopoisk_id, full_data=False)
            if not data:
                failed += 1
                logger.warning(f"Failed to fetch data for movie {movie.kinopoisk_id}")
                continue
            
            # Обновляем поля только если они есть в ответе
            updated_fields = []
            
            if data.get("poster_url"):
                movie.poster_url = data["poster_url"]
                updated_fields.append("poster_url")
            
            if data.get("description"):
                movie.description = data["description"]
                updated_fields.append("description")
            
            if data.get("rating") is not None:
                movie.rating = data["rating"]
                updated_fields.append("rating")
            
            if data.get("title_original"):
                movie.title_original = data["title_original"]
                updated_fields.append("title_original")
            
            if updated_fields:
                db.add(movie)
                updated += 1
                logger.info(f"Updated movie {movie.kinopoisk_id}: {movie.title} - fields: {', '.join(updated_fields)}")
            else:
                skipped += 1
                logger.info(f"No new data for movie {movie.kinopoisk_id}")
        
        db.commit()
        logger.info("=" * 50)
        logger.info(f"Update complete:")
        logger.info(f"  Updated: {updated}")
        logger.info(f"  Skipped: {skipped}")
        logger.info(f"  Failed: {failed}")
        logger.info("=" * 50)
        
        # Если нечего было обновлять - добавляем новые фильмы
        if updated == 0:
            logger.info("No movies to update. Adding 5 new popular movies...")
            _add_new_movies(db)
        
    except Exception as e:
        logger.error(f"Error updating movies: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def _add_new_movies(db: Session) -> None:
    """
    Добавляет 5 новых популярных фильмов в БД.
    
    Args:
        db: Сессия БД
    """
    # Список популярных фильмов (kinopoisk_id) - 5 штук
    popular_movies = [
        301,   # Матрица (1999)
        435,   # Зеленая миля (1999)
        328,   # Побег из Шоушенка (1994)
        448,   # Форрест Гамп (1994)
        8124,  # Список Шиндлера (1993)
    ]
    
    added = 0
    skipped = 0
    failed = 0
    
    for kinopoisk_id in popular_movies:
        # Проверяем, есть ли уже такой фильм в БД
        existing = movie_service.get_movie_by_kinopoisk_id(db, kinopoisk_id)
        if existing:
            logger.info(f"Movie {kinopoisk_id} already exists, skipping")
            skipped += 1
            continue
        
        logger.info(f"Fetching full data for movie {kinopoisk_id}...")
        
        # Получаем полные данные из API для создания нового фильма
        movie_data = movie_service.fetch_movie_from_kinopoisk(kinopoisk_id, full_data=True)
        if not movie_data:
            logger.warning(f"Failed to fetch full data for movie {kinopoisk_id}")
            failed += 1
            continue
        
        # Создаем новый фильм
        try:
            new_movie = movie_service.create_movie(
                db=db,
                kinopoisk_id=movie_data["kinopoisk_id"],
                title=movie_data["title"],
                year=movie_data["year"],
                genre=movie_data["genre"],
                poster_url=movie_data["poster_url"],
                title_original=movie_data.get("title_original"),
                description=movie_data.get("description"),
                rating=movie_data.get("rating"),
            )
            added += 1
            logger.info(f"✅ Added new movie: {new_movie.title} ({new_movie.year})")
        except Exception as e:
            logger.error(f"Failed to create movie {kinopoisk_id}: {e}", exc_info=True)
            failed += 1
    
    db.commit()
    logger.info("=" * 50)
    logger.info(f"New movies added:")
    logger.info(f"  Added: {added}")
    logger.info(f"  Skipped (already exist): {skipped}")
    logger.info(f"  Failed: {failed}")
    logger.info("=" * 50)


if __name__ == "__main__":
    update_movies()

