from typing import Optional, Sequence, Dict

import httpx
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
        stmt = select(Movie).order_by(func.random()).limit(1)
        return db.execute(stmt).scalar_one_or_none()


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