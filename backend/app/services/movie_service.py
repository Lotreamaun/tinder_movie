from typing import Optional, Sequence, Dict, List

import httpx
import random
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.movie import Movie
from app.config import settings
from app.logging_config import logger

class MovieService:
    def create_movie(
        self,
        db: Session,
        kinopoisk_id: int,
        title: str,
        year: int,
        genre: str,
        poster_url: str,
        title_original: Optional[str] = None,
        description: Optional[str] = None,
        rating: Optional[float] = None,
    ) -> Movie:
        movie = Movie(
            kinopoisk_id=kinopoisk_id,
            title=title,
            title_original=title_original,
            year=year,
            genre=genre,
            poster_url=poster_url,
            description=description,
            rating=rating,
        )
        db.add(movie)
        db.commit()
        db.refresh(movie)
        return movie
    
    def get_random_movie(self, db: Session) -> Optional[Movie]:
        """
        Получает случайный фильм. Автоматически поддерживает запас фильмов в БД.

        NOTE: Текущая реализация использует простую ротацию контента (удаление старых фильмов).
        TODO: В будущем реализовать персонализированную систему:
        - Отслеживать просмотренные фильмы для каждого пользователя
        - Показывать только непросмотренные фильмы
        - Персонализировать рекомендации на основе предпочтений

        Returns:
            Случайный фильм или None если нет фильмов и не удалось загрузить
        """
        from app.config import settings

        # Считаем количество фильмов в БД
        total_movies = db.query(func.count(Movie.id)).scalar()

        # Если фильмов меньше порога - загружаем новые
        if total_movies < settings.MOVIES_LOAD_THRESHOLD:
            needed = settings.MIN_MOVIES_COUNT - total_movies
            load_count = min(needed, settings.MOVIES_LOAD_BATCH)

            logger.info(f"Only {total_movies} movies in DB (threshold: {settings.MOVIES_LOAD_THRESHOLD}), loading {load_count} more...")
            loaded = self.load_batch_movies(db, count=load_count)
            if loaded == 0 and total_movies == 0:
                logger.error("No movies in DB and failed to load new ones")
                return None

            # TODO: В будущем заменить на персонализированную систему просмотренных фильмов
            # Сейчас используем простую ротацию контента для MVP
            # Идея: добавить таблицу user_viewed_movies для отслеживания просмотренных фильмов каждым пользователем
            # Это позволит показывать только новые фильмы и персонализировать рекомендации

            # После загрузки новых фильмов - очищаем старые для ротации контента
            self.cleanup_old_movies(db)

        # Получаем случайный фильм
        stmt = select(Movie).order_by(func.random()).limit(1)
        movie = db.execute(stmt).scalar_one_or_none()

        if movie:
            logger.debug(f"Returning random movie: {movie.title} (ID: {movie.id})")
        else:
            logger.warning("No movies available after attempting to load more")

        return movie


    def get_movie_by_id(self, db: Session, id: str) -> Optional[Movie]:
        return db.get(Movie, id)


    def get_movie_by_kinopoisk_id(self, db: Session, kinopoisk_id: int) -> Optional[Movie]:
        stmt = select(Movie).where(Movie.kinopoisk_id == kinopoisk_id)
        return db.execute(stmt).scalar_one_or_none()


    def list_movies(self, db: Session, limit: int = 50, offset: int = 0) -> Sequence[Movie]:
        stmt = select(Movie).order_by(Movie.created_at.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars())


    def update_movie_active(self, db: Session, movie: Movie, is_active: bool) -> Movie:
        movie.is_active = is_active
        db.add(movie)
        db.commit()
        db.refresh(movie)
        return movie


    def delete_movie(self, db: Session, movie: Movie) -> None:
        db.delete(movie)
        db.commit()

    def get_top_movies_from_kinopoisk(self, page: int = 1, limit: int = 10) -> List[Dict]:
        """
        Получает топ фильмов из Kinopoisk API.

        Args:
            page: Номер страницы (начиная с 1)
            limit: Количество фильмов на страницу (макс 50)

        Returns:
            Список словарей с данными фильмов для создания в БД
        """
        if not settings.KINOPOISK_API_KEY:
            logger.warning("KINOPOISK_API_KEY not set, cannot load movies")
            return []

        # Ограничиваем параметры разумными пределами
        page = max(1, min(page, 100))  # Не более 100 страниц
        limit = max(1, min(limit, 50))  # Не более 50 фильмов за раз

        url = f"{settings.KINOPOISK_BASE_URL}/films/top"
        params = {
            "type": "TOP_250_BEST_FILMS",  # Топ 250 лучших фильмов
            "page": page
        }
        headers = {"X-API-KEY": settings.KINOPOISK_API_KEY}

        logger.info(f"Fetching top movies from Kinopoisk API: page {page}, limit {limit}")

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()

                films = data.get("films", [])
                if not films:
                    logger.warning(f"No films found in Kinopoisk API response")
                    return []

                result = []
                for film in films[:limit]:  # Ограничиваем по limit
                    kinopoisk_id = film.get("filmId") or film.get("kinopoiskId")
                    if not kinopoisk_id:
                        logger.warning(f"Skipping film without ID: {film}")
                        continue

                    # Получаем полные данные фильма
                    movie_data = self.fetch_movie_from_kinopoisk(kinopoisk_id, full_data=True)
                    if movie_data:
                        result.append(movie_data)
                    else:
                        logger.warning(f"Could not fetch full data for movie {kinopoisk_id}")

                logger.info(f"Successfully loaded {len(result)} movies from Kinopoisk")
                return result

        except Exception as e:
            logger.error(f"Failed to fetch top movies from Kinopoisk: {e}", exc_info=True)
            return []

    def load_batch_movies(self, db: Session, count: int = 10) -> int:
        """
        Загружает пачку фильмов из Kinopoisk API и сохраняет в БД.

        Args:
            db: Сессия БД
            count: Количество фильмов для загрузки

        Returns:
            Количество успешно загруженных фильмов
        """
        logger.info(f"Loading {count} movies from Kinopoisk API")

        loaded_count = 0
        page = 1

        while loaded_count < count:
            # Получаем топ фильмы (по 20 за раз для эффективности)
            batch_size = min(20, count - loaded_count)
            movies_data = self.get_top_movies_from_kinopoisk(page=page, limit=batch_size)

            if not movies_data:
                logger.warning(f"No more movies available from Kinopoisk API (page {page})")
                break

            # Сохраняем фильмы в БД (только те, которых еще нет)
            for movie_data in movies_data:
                if loaded_count >= count:
                    break

                kinopoisk_id = movie_data["kinopoisk_id"]

                # Проверяем, есть ли уже такой фильм
                existing = self.get_movie_by_kinopoisk_id(db, kinopoisk_id)
                if existing:
                    logger.debug(f"Movie {kinopoisk_id} already exists, skipping")
                    continue

                try:
                    # Создаем фильм в БД
                    movie = self.create_movie(
                        db=db,
                        kinopoisk_id=kinopoisk_id,
                        title=movie_data["title"],
                        year=movie_data["year"],
                        genre=movie_data["genre"],
                        poster_url=movie_data["poster_url"],
                        title_original=movie_data.get("title_original"),
                        description=movie_data.get("description"),
                        rating=movie_data.get("rating"),
                    )
                    loaded_count += 1
                    logger.debug(f"Loaded movie: {movie.title} (ID: {movie.id})")

                except Exception as e:
                    logger.error(f"Failed to create movie {kinopoisk_id}: {e}")
                    continue

            page += 1

            # Защита от бесконечного цикла (максимум 10 страниц)
            if page > 10:
                logger.warning("Reached maximum page limit (10), stopping batch load")
                break

        logger.info(f"Successfully loaded {loaded_count} new movies")
        return loaded_count

    def cleanup_old_movies(self, db: Session) -> int:
        """
        Удаляет старые фильмы, оставляя только последние MAX_MOVIES_IN_DB.

        Args:
            db: Сессия БД

        Returns:
            Количество удаленных фильмов
        """
        from app.config import settings

        # Получаем общее количество фильмов
        total_movies = db.query(func.count(Movie.id)).scalar()

        if total_movies <= settings.MAX_MOVIES_IN_DB:
            return 0  # Ничего удалять не нужно

        # Удаляем старые фильмы, оставляя только последние MAX_MOVIES_IN_DB
        movies_to_delete = total_movies - settings.MAX_MOVIES_IN_DB

        # Получаем ID фильмов для удаления (самые старые по дате создания)
        stmt = select(Movie.id).order_by(Movie.created_at.asc()).limit(movies_to_delete)
        movie_ids_to_delete = [row[0] for row in db.execute(stmt).fetchall()]

        if not movie_ids_to_delete:
            return 0

        # Удаляем фильмы
        delete_stmt = select(Movie).where(Movie.id.in_(movie_ids_to_delete))
        movies_to_delete_objs = list(db.execute(delete_stmt).scalars())

        for movie in movies_to_delete_objs:
            db.delete(movie)

        db.commit()
        logger.info(f"Cleaned up {len(movie_ids_to_delete)} old movies")
        return len(movie_ids_to_delete)

    def fetch_movie_from_kinopoisk(self, kinopoisk_id: int, full_data: bool = False) -> Optional[Dict]:
        """
        Получает данные о фильме из Kinopoisk API.
        
        Args:
            kinopoisk_id: ID фильма в Kinopoisk
            full_data: Если True, возвращает все поля для создания фильма (title, year, genre, etc.)
                      Если False, возвращает только поля для обновления (poster_url, description, rating, title_original)
            
        Returns:
            dict с данными фильма или None при ошибке
        """
        if not settings.KINOPOISK_API_KEY:
            logger.warning("KINOPOISK_API_KEY not set, skipping API call")
            return None
        
        url = f"{settings.KINOPOISK_BASE_URL}/films/{kinopoisk_id}"
        headers = {"X-API-KEY": settings.KINOPOISK_API_KEY}
        
        logger.debug(f"Requesting Kinopoisk API: {url}")
        logger.debug(f"Headers: X-API-KEY={'*' * (len(settings.KINOPOISK_API_KEY) - 4) + settings.KINOPOISK_API_KEY[-4:] if len(settings.KINOPOISK_API_KEY) > 4 else '****'}")
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                
                # Логируем детали ответа при ошибке
                if response.status_code != 200:
                    logger.error(f"Kinopoisk API returned status {response.status_code} for {kinopoisk_id}")
                    logger.error(f"Response text: {response.text[:500]}")
                    try:
                        error_data = response.json()
                        logger.error(f"Response JSON: {error_data}")
                    except:
                        pass
                
                response.raise_for_status()
                data = response.json()
                
                # Если нужны полные данные для создания фильма
                if full_data:
                    # Название (обязательное)
                    title = data.get("nameRu") or data.get("nameEn") or data.get("nameOriginal") or ""
                    if not title:
                        logger.warning(f"No title found for movie {kinopoisk_id}")
                        return None
                    
                    # Год (обязательное)
                    year = data.get("year")
                    if not year:
                        logger.warning(f"No year found for movie {kinopoisk_id}")
                        return None
                    
                    # Жанр (обязательное) - берем первый жанр
                    genres = data.get("genres", [])
                    genre = "Неизвестно"
                    if genres and isinstance(genres, list) and len(genres) > 0:
                        if isinstance(genres[0], dict):
                            genre = genres[0].get("genre", "Неизвестно")
                        else:
                            genre = str(genres[0])
                    
                    # Постер (обязательное, но может быть пустым)
                    poster_url = data.get("posterUrl", "")
                    
                    # Описание (опциональное)
                    description = data.get("description")
                    
                    # Рейтинг (опциональное)
                    rating = None
                    rating_value = data.get("rating") or data.get("ratingKinopoisk") or data.get("ratingImdb")
                    if rating_value:
                        try:
                            rating = float(rating_value)
                        except (ValueError, TypeError):
                            pass
                    
                    # Оригинальное название (опциональное)
                    title_original = data.get("nameOriginal")
                    
                    return {
                        "kinopoisk_id": kinopoisk_id,
                        "title": title,
                        "year": int(year),
                        "genre": genre,
                        "poster_url": poster_url,
                        "description": description,
                        "rating": rating,
                        "title_original": title_original,
                    }
                else:
                    # Только поля для обновления существующего фильма
                    result = {}
                    
                    # Постер
                    if data.get("posterUrl"):
                        result["poster_url"] = data["posterUrl"]
                    else:
                        result["poster_url"] = ""  # Обязательное поле
                    
                    # Описание
                    if data.get("description"):
                        result["description"] = data["description"]
                    
                    # Рейтинг (может быть в разных полях)
                    rating = data.get("rating") or data.get("ratingKinopoisk") or data.get("ratingImdb")
                    if rating:
                        try:
                            result["rating"] = float(rating)
                        except (ValueError, TypeError):
                            pass
                    
                    # Оригинальное название
                    if data.get("nameOriginal"):
                        result["title_original"] = data["nameOriginal"]
                    
                    return result if result else None
                
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            try:
                error_text = e.response.text[:500]
                logger.error(f"Kinopoisk API HTTP error {status_code} for {kinopoisk_id}")
                logger.error(f"Response: {error_text}")
                try:
                    error_json = e.response.json()
                    logger.error(f"Error details: {error_json}")
                except:
                    pass
            except:
                logger.error(f"Kinopoisk API HTTP error {status_code} for {kinopoisk_id} (could not read response)")
            
            if status_code == 404:
                logger.warning(f"Movie {kinopoisk_id} not found in Kinopoisk API")
            elif status_code == 400:
                logger.error(f"Bad Request (400) - check URL format and API key: {url}")
            elif status_code == 401:
                logger.error(f"Unauthorized (401) - check KINOPOISK_API_KEY")
            elif status_code == 402:
                logger.error(f"Payment Required (402) - API key limit exceeded")
            elif status_code == 429:
                logger.error(f"Too Many Requests (429) - rate limit exceeded")
            else:
                logger.error(f"Kinopoisk API error for {kinopoisk_id}: {status_code}")
            return None
        except httpx.TimeoutException:
            logger.error(f"Timeout while fetching movie {kinopoisk_id} from Kinopoisk API")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch movie {kinopoisk_id} from Kinopoisk: {e}", exc_info=True)
            return None

movie_service = MovieService()