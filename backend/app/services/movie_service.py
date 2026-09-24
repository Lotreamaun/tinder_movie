from dataclasses import dataclass
from typing import Optional, Sequence, Dict, List

import httpx
import random
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.movie import Movie
from app.models.user import User
from app.config import settings
from app.logging_config import logger
from app.services.deck_service import deck_service


@dataclass
class LoadBatchResult:
    """Результат одной попытки догрузки каталога (design.md, Decision 6)."""

    loaded: int
    stop_reason: str  # "count" | "budget" | "pass_end" | "error"
    new_in_pass: Optional[int] = None  # заполнено только для "pass_end"


@dataclass
class _CollectionPage:
    """Одна страница подборки Kinopoisk после маппинга и отсева."""

    items: List[Dict]  # новые фильмы страницы (известные и не-FILM отсеяны)
    total_pages: int
    raw_count: int  # число элементов до отсева — для определения конца подборки


class MovieService:
    def __init__(self) -> None:
        # Курсор прохода по настроенным подборкам Kinopoisk (design.md,
        # Decision 3). Доступ сериализован _growth_lock в deck_service:
        # догрузка идёт не более чем в одном фоновом потоке на процесс,
        # отдельная синхронизация курсора не нужна.
        self._collection_index = 0
        self._next_page = 1
        self._new_in_pass = 0

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
    
    def get_random_movie(
        self,
        db: Session,
        user: Optional[User] = None,
        room_code: Optional[str] = None,
    ) -> Optional[Movie]:
        """
        Получает следующий фильм для свайпов.

        Для участника комнаты (room_code + user) возвращает фильм из общего
        упорядоченного колода комнаты (см. DeckService). Вне комнаты — случайный
        фильм из общей базы. Автоматически поддерживает запас фильмов в БД.

        NOTE: Текущая реализация использует простую ротацию контента (удаление старых фильмов).
        TODO: В будущем реализовать персонализированную систему:
        - Отслеживать просмотренные фильмы для каждого пользователя
        - Показывать только непросмотренные фильмы
        - Персонализировать рекомендации на основе предпочтений

        Returns:
            Фильм или None если нет фильмов и не удалось загрузить
        """
        from app.config import settings

        # В комнате фильмы выдаются из общего колода комнаты.
        if room_code and user is not None:
            return deck_service.get_next_movie_for_room(db=db, user=user, room_code=room_code)

        # Считаем количество фильмов в БД
        total_movies = db.query(func.count(Movie.id)).scalar()

        # Если фильмов меньше порога - загружаем новые
        if total_movies < settings.MOVIES_LOAD_THRESHOLD:
            needed = settings.MIN_MOVIES_COUNT - total_movies
            load_count = min(needed, settings.MOVIES_LOAD_BATCH)

            logger.info(f"Only {total_movies} movies in DB (threshold: {settings.MOVIES_LOAD_THRESHOLD}), loading {load_count} more...")
            result = self.load_batch_movies(db, count=load_count)
            if result.loaded == 0 and total_movies == 0:
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

    def _fetch_collection_page(self, db: Session, collection: str, page: int) -> Optional[_CollectionPage]:
        """Загружает одну страницу подборки Kinopoisk `/films/collections`.

        Каждый элемент уже содержит все поля, нужные для создания фильма
        (design.md, Decision 1) — отдельный запрос полных данных не нужен.

        Returns:
            `_CollectionPage` с уже отфильтрованными новыми фильмами
            (известные по `kinopoisk_id` и не-`FILM` отброшены) и метаданными
            для определения конца подборки; None при ошибке запроса или
            исчерпании квоты (402) — пагинацию в этом случае останавливают.
        """
        if not settings.KINOPOISK_API_KEY:
            logger.warning("KINOPOISK_API_KEY not set, cannot load movies")
            return None

        url = f"{settings.KINOPOISK_BASE_URL}/films/collections"
        params = {"type": collection, "page": page}
        headers = {"X-API-KEY": settings.KINOPOISK_API_KEY}

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            # 402 (квота исчерпана) — ожидаемая ситуация, а не ошибка кода:
            # одна строка WARNING без traceback (design.md fix-movie-catalog-exhaustion, Decision 4).
            if status_code == 402:
                logger.warning(
                    f"Kinopoisk API quota exceeded (402) while fetching collection={collection} page={page}"
                )
            else:
                logger.error(
                    f"Kinopoisk API HTTP error {status_code} for collection={collection} page={page}",
                    exc_info=True,
                )
            return None
        except Exception as e:
            logger.error(
                f"Failed to fetch collection={collection} page={page} from Kinopoisk: {e}", exc_info=True
            )
            return None

        raw_items = data.get("items", [])
        total_pages = data.get("totalPages")
        if not isinstance(total_pages, int) or total_pages < 1:
            # Нет totalPages в ответе — конец подборки определяем по пустому
            # items на следующей странице (design.md, Decision 2).
            total_pages = page + 1 if raw_items else page

        items = []
        for item in raw_items:
            item_type = item.get("type")
            # Элементы без type принимаются для совместимости со старым
            # форматом ответа (design.md, Decision 4); явные не-FILM отсеиваются.
            if item_type is not None and item_type != "FILM":
                continue

            kinopoisk_id = item.get("kinopoiskId") or item.get("filmId")
            if not kinopoisk_id:
                continue

            # Фильм уже есть в БД — не тратим место в пачке на него.
            if self.get_movie_by_kinopoisk_id(db, kinopoisk_id):
                continue

            movie_data = self._map_kinopoisk_movie_data(item, kinopoisk_id)
            if movie_data:
                items.append(movie_data)

        return _CollectionPage(items=items, total_pages=total_pages, raw_count=len(raw_items))

    def load_batch_movies(self, db: Session, count: int = 10) -> LoadBatchResult:
        """
        Догружает пачку новых фильмов из настроенных подборок Kinopoisk.

        Проход по подборкам продолжается с курсора, где остановилась
        предыдущая попытка (design.md, Decision 3), а не с первой страницы
        первой подборки. Попытка останавливается по первому из условий:
        набрано `count` новых фильмов, исчерпан бюджет страниц попытки
        (`CATALOG_GROWTH_MAX_PAGES`), дошли до конца полного прохода всех
        подборок (`pass_end`), либо источник вернул ошибку (курсор в этом
        случае не сдвигается за проблемную страницу).

        Args:
            db: Сессия БД
            count: Сколько новых фильмов набрать за попытку

        Returns:
            `LoadBatchResult` с числом загруженных фильмов и причиной остановки.
        """
        collections = settings.KINOPOISK_COLLECTIONS
        if not collections:
            logger.error("KINOPOISK_COLLECTIONS is empty, cannot load movies")
            return LoadBatchResult(loaded=0, stop_reason="error")

        loaded_count = 0
        pages_fetched = 0

        while True:
            if loaded_count >= count:
                return LoadBatchResult(loaded=loaded_count, stop_reason="count")
            if pages_fetched >= settings.CATALOG_GROWTH_MAX_PAGES:
                return LoadBatchResult(loaded=loaded_count, stop_reason="budget")

            collection = collections[self._collection_index]
            page = self._next_page
            page_result = self._fetch_collection_page(db, collection, page)
            pages_fetched += 1

            if page_result is None:
                return LoadBatchResult(loaded=loaded_count, stop_reason="error")

            new_on_page = 0
            for movie_data in page_result.items:
                if loaded_count >= count:
                    break
                try:
                    movie = self.create_movie(
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
                    loaded_count += 1
                    new_on_page += 1
                    logger.debug(f"Loaded movie: {movie.title} (ID: {movie.id})")
                except Exception as e:
                    logger.error(f"Failed to create movie {movie_data.get('kinopoisk_id')}: {e}")
                    continue

            self._new_in_pass += new_on_page
            logger.info(
                "Catalog growth page collection=%s page=%s/%s new=%s",
                collection,
                page,
                page_result.total_pages,
                new_on_page,
            )

            collection_finished = page_result.raw_count == 0 or page >= page_result.total_pages
            if collection_finished and self._collection_index + 1 >= len(collections):
                # Конец полного прохода: попытка останавливается здесь и не
                # начинает новый проход в остатке бюджета (design.md, Decision 2/6).
                new_in_pass = self._new_in_pass
                self._collection_index = 0
                self._next_page = 1
                self._new_in_pass = 0
                return LoadBatchResult(loaded=loaded_count, stop_reason="pass_end", new_in_pass=new_in_pass)

            if collection_finished:
                self._collection_index += 1
                self._next_page = 1
            else:
                self._next_page = page + 1

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

    def _map_kinopoisk_movie_data(self, data: Dict, kinopoisk_id: int) -> Optional[Dict]:
        """Маппит ответ Kinopoisk (формат `/films/{id}` и `/films/collections`,
        поля совпадают — design.md, Context) в поля для создания `Movie`.

        Используется и `fetch_movie_from_kinopoisk(full_data=True)`, и выборкой
        страницы подборки, чтобы правила отбраковки не разъехались
        (design.md, Decision 1).

        Returns:
            dict с полями `Movie` или None, если нет обязательных title/year.
        """
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
                    return self._map_kinopoisk_movie_data(data, kinopoisk_id)
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

            # 402 (квота исчерпана) — ожидаемая ситуация, а не ошибка кода:
            # одна строка WARNING без traceback и без подробностей ответа
            # (design.md fix-movie-catalog-exhaustion, Decision 4).
            if status_code == 402:
                logger.warning(f"Kinopoisk API quota exceeded (402) while fetching movie {kinopoisk_id}")
                return None

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