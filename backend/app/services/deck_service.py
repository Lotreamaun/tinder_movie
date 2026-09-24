"""Сервис общего колода фильмов комнаты.

Каждая комната имеет один упорядоченный колод фильмов (таблица room_decks).
Участники движутся по нему независимо: у каждого своя позиция-курсор
(таблица room_deck_positions), которую продвигает каждый запрос «следующего
фильма». Поэтому параллельные запросы одного участника (предзагрузка фронта)
возвращают разные фильмы без повторов, а последовательность колода общая —
матч между участниками достижим.

Алгоритм выдачи (design.md, D3): prune → clamp → scan → advance.
"""
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import and_, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import logger
from app.models.movie import Movie
from app.models.room import Room
from app.models.room_deck import RoomDeck
from app.models.room_deck_position import RoomDeckPosition
from app.models.swipe import UserSwipe
from app.models.user import User
from app.services.room_service import room_service
from app.services.room_session import get_session_start

# Размер пачки при создании/пополнении колода (см. design.md, N=50).
DECK_BATCH_SIZE = 50


class DeckService:
    """Управление общим колодом фильмов комнаты."""

    def __init__(self) -> None:
        # In-process guard фоновой догрузки каталога (design.md, Decision 1).
        self._growth_lock = threading.Lock()
        # Пауза после пустой/неудачной догрузки — до этого момента новые
        # попытки не запускаются (design.md, Decision 8). In-memory,
        # сбрасывается при рестарте процесса — как и _growth_lock.
        self._growth_cooldown_until: Optional[datetime] = None

    def get_next_movie_for_room(self, db: Session, user: User, room_code: str) -> Optional[Movie]:
        """Возвращает следующий по общему колоду фильм для участника комнаты.

        Каждый вызов продвигает позицию участника вперёд, поэтому повторные и
        параллельные запросы возвращают разные фильмы. Если колода нет —
        создаёт его; если позиция дошла до конца — пополняет колод.
        Возвращает None, если фильм не найден.

        Транзакция закрывается одним финальным commit: он атомарно персистит
        создание позиции (если оно было), её продвижение и возможное пополнение
        колоды (design.md, D1/D2).
        """
        room = room_service.get_room_by_code(db, room_code)
        if not room or user.telegram_id not in room.participants:
            return None

        deck = self._get_or_create_deck(db, room)
        # FOR UPDATE на строку позиции сериализует параллельные запросы
        # одного участника (design.md, D2): они получают разные фильмы.
        position = self._get_or_create_position(db, user.id, room.id)

        swiped = self._swiped_movie_ids(db, user, room)
        # Проактивная догрузка каталога по порогу — в фоне, ответ её не ждёт
        # (design.md, Decision 1/2).
        self._maybe_grow_catalog(db, user, room, swiped)

        movie, index = self._next_available(db, deck, position.position, swiped)
        if movie is not None:
            logger.info("Movie served path=deck room=%s user=%s", room.id, user.id)
        else:
            # Дошли до конца колода — пополняем и продолжаем scan (D3, шаг 5).
            self._replenish_deck(db, deck, swiped, position.position)
            movie, index = self._next_available(db, deck, position.position, swiped)
            if movie is not None:
                logger.info("Movie served path=replenished-from-catalog room=%s user=%s", room.id, user.id)
            else:
                # Каталог исчерпан (фоновая догрузка ещё не завершилась или
                # не нашла новых фильмов): отдаём случайный фильм повторно, по
                # возможности минуя просвайпанные, чтобы фид не заканчивался 404.
                logger.info("Movie served path=random-fallback room=%s user=%s", room.id, user.id)
                return self._random_movie(db, exclude=swiped)

        # Advance (D3, шаг 6): следующий запрос начнёт с индекса после выданного.
        position.position = index + 1
        position.updated_at = datetime.now(timezone.utc)
        db.add(position)
        db.commit()
        db.refresh(position)
        return movie

    def _get_or_create_deck(self, db: Session, room: Room) -> RoomDeck:
        """Возвращает колод комнаты, создавая его при первом запросе (lazy)."""
        deck = self._get_deck(db, room.id, lock=True)
        if deck:
            return deck

        exclude = self._swiped_movie_ids_in_room(db, room)
        movie_ids = self._sample_movie_ids(db, exclude=exclude)
        deck = RoomDeck(room_code=room.id, movie_ids=movie_ids)
        db.add(deck)
        try:
            db.commit()
        except IntegrityError:
            # Конкурентное создание: другой запрос уже создал колод.
            db.rollback()
            deck = self._get_deck(db, room.id, lock=True)
            if deck is None:
                raise
        db.refresh(deck)
        return deck

    def _get_or_create_position(self, db: Session, user_id: UUID, room_code: str) -> RoomDeckPosition:
        """Возвращает позицию участника в колоде, создавая её при первом запросе.

        Создание НЕ коммитится отдельно (design.md, D1): вставка строки неявно
        держит её блокировку до финального commit вызывающего кода, где позиция
        продвигается. Конкурентный запрос блокируется на этой строке и после
        rollback читает уже продвинутую позицию — дубликатов при параллельной
        предзагрузке не возникает.
        """
        position = self._get_position(db, user_id, room_code, lock=True)
        if position:
            return position

        position = RoomDeckPosition(user_id=user_id, room_code=room_code, position=0)
        db.add(position)
        try:
            db.flush()
        except IntegrityError:
            # Конкурентное создание: другой запрос уже создал строку позиции.
            db.rollback()
            position = self._get_position(db, user_id, room_code, lock=True)
            if position is None:
                raise
        return position

    def _next_available(
        self,
        db: Session,
        deck: RoomDeck,
        start_index: int,
        swiped: Set[UUID],
    ) -> Tuple[Optional[Movie], Optional[int]]:
        """Prune → clamp → scan: следующий существующий непросвайпнутый фильм.

        Удалённые фильмы (ротация) вычищаются из колода и пропускаются (prune);
        позиция ограничивается длиной колода (clamp); scan идёт от позиции,
        пропуская уже просвайпнутые участником фильмы.

        Returns:
            (movie, index): фильм и его индекс в (вычищенном) колоде,
            либо (None, None), если фильм не найден.
        """
        ids = [UUID(movie_id) for movie_id in deck.movie_ids]
        if not ids:
            return None, None

        existing_ids = set(db.execute(select(Movie.id).where(Movie.id.in_(ids))).scalars())

        pruned = [movie_id for movie_id in ids if movie_id in existing_ids]
        if len(pruned) != len(deck.movie_ids):
            deck.movie_ids = [str(movie_id) for movie_id in pruned]

        start = min(start_index, len(pruned))
        for i in range(start, len(pruned)):
            movie_id = pruned[i]
            if movie_id in swiped:
                continue
            movie = db.get(Movie, movie_id)
            if movie is not None:
                return movie, i
        return None, None

    def _replenish_deck(self, db: Session, deck: RoomDeck, swiped: Set[UUID], position: int) -> None:
        """Пополняет колод новой пачкой, блокируя строку на время записи.

        Исключаются только свайпы текущего участника в текущей сессии (`swiped`,
        как и при scan) — фильмы, которые свайпнули другие участники, не
        блокируют пополнение, иначе свайпы из других комнат (подбор по составу
        участников) выжимают каталог.

        Сначала берутся фильмы, которых ещё нет в колоде. Если таких не осталось —
        рецикл (design.md fix-movie-catalog-exhaustion, Decision 6): уже бывшие в
        колоде фильмы, кроме последних `DECK_BATCH_SIZE` перед курсором участника —
        они могут ещё лежать в очереди предзагрузки фронта и не быть свайпнуты.

        Коммит здесь не выполняется (design.md, D2): транзакционная граница —
        за внешним `get_next_movie_for_room`, чтобы персист позиции и пополнение
        колода не разрывались промежуточным commit.
        """
        locked = self._get_deck(db, deck.room_code, lock=True)
        if locked is None:
            raise RuntimeError(f"Deck for room {deck.room_code} disappeared")
        deck = locked

        path = "new"
        new_ids = self._sample_movie_ids(db, exclude={UUID(movie_id) for movie_id in deck.movie_ids} | swiped)
        if not new_ids:
            path = "recycle"
            recent = deck.movie_ids[max(0, position - DECK_BATCH_SIZE) : position]
            new_ids = self._sample_movie_ids(db, exclude={UUID(movie_id) for movie_id in recent} | swiped)
        if not new_ids:
            return

        deck.movie_ids = deck.movie_ids + new_ids
        logger.info(
            "Replenished deck for room %s with %d movies (%s)", deck.room_code, len(new_ids), path
        )

    def _maybe_grow_catalog(self, db: Session, user: User, room: Room, swiped: Set[UUID]) -> None:
        """Запускает фоновую догрузку, если у участника мало непросвайпанных фильмов."""
        stmt = select(func.count(Movie.id))
        if swiped:
            stmt = stmt.where(Movie.id.not_in(list(swiped)))
        remaining = db.execute(stmt).scalar_one()
        if remaining >= settings.DECK_CATALOG_LOW_THRESHOLD:
            return
        if self._growth_cooldown_until is not None and datetime.now(timezone.utc) < self._growth_cooldown_until:
            return
        # Идентификаторы читаются здесь, в потоке запроса: ORM-объекты сессии
        # запроса нельзя трогать из фонового потока.
        if self._start_background_growth(user.id, room.id):
            logger.info(
                "Background catalog growth started room=%s user=%s remaining=%d",
                room.id,
                user.id,
                remaining,
            )

    def _start_background_growth(self, user_id: UUID, room_code: str) -> bool:
        """Стартует `_grow_catalog` в daemon-потоке, если догрузка ещё не идёт.

        In-process guard (design.md, Decision 1): лок берётся неблокирующе и
        снимается в `finally` фонового задания, поэтому одновременно идёт не
        больше одной догрузки на процесс.

        Returns:
            True, если поток запущен; False, если догрузка уже идёт.
        """
        if not self._growth_lock.acquire(blocking=False):
            return False
        thread = threading.Thread(
            target=self._run_background_growth,
            args=(user_id, room_code),
            name="catalog-growth",
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            self._growth_lock.release()
            raise
        return True

    def _run_background_growth(self, user_id: UUID, room_code: str) -> None:
        """Тело фонового потока: догрузка с гарантированным снятием guard.

        Пауза перед следующей попыткой выбирается по причине остановки
        попытки (design.md, Decision 6): ошибка источника — короткая пауза;
        конец полного прохода без единого нового фильма (подборки
        исчерпаны) — длинная; во всех остальных случаях (бюджет страниц,
        набран `count`, конец прохода с новыми фильмами) — паузы нет, проход
        не закончен или только что подтвердил, что подборки не исчерпаны.
        """
        try:
            result = self._grow_catalog(user_id, room_code)
            if result.stop_reason == "error":
                self._set_growth_cooldown(
                    timedelta(minutes=settings.CATALOG_GROWTH_COOLDOWN_MINUTES), "error"
                )
            elif result.stop_reason == "pass_end" and not result.new_in_pass:
                self._set_growth_cooldown(
                    timedelta(hours=settings.CATALOG_SOURCES_EXHAUSTED_COOLDOWN_HOURS),
                    "sources_exhausted",
                )
        except Exception as e:
            logger.error("Background catalog growth failed room=%s: %s", room_code, e, exc_info=True)
            self._set_growth_cooldown(
                timedelta(minutes=settings.CATALOG_GROWTH_COOLDOWN_MINUTES), "error"
            )
        finally:
            self._growth_lock.release()

    def _set_growth_cooldown(self, duration: timedelta, reason: str) -> None:
        """Ставит паузу перед следующей попыткой догрузки (design.md, Decision 6)."""
        self._growth_cooldown_until = datetime.now(timezone.utc) + duration
        logger.info(
            "Catalog growth cooldown started reason=%s until=%s",
            reason,
            self._growth_cooldown_until.isoformat(),
        )

    def _grow_catalog(self, user_id: UUID, room_code: str) -> "LoadBatchResult":
        """Догружает новые фильмы в общий каталог из Kinopoisk.

        Выполняется на ОТДЕЛЬНОЙ сессии (не сессии запроса), потому что
        `load_batch_movies` коммитит после каждого фильма — на сессии с
        открытым `FOR UPDATE` на deck/position это нарушило бы инвариант
        единственного финального commit и держало бы блокировки на время
        HTTP-запросов к Kinopoisk (design.md, Decision 1). Сессия закрывается
        независимо от результата; закоммиченные фильмы станут видны следующим
        запросам через обычное пополнение колода.
        """
        from app.database import SessionLocal
        from app.services.movie_service import movie_service

        session = SessionLocal()
        try:
            result = movie_service.load_batch_movies(session, count=settings.MOVIES_LOAD_BATCH)
            logger.info(
                "Grew catalog by %d movies (room=%s user=%s stop_reason=%s)",
                result.loaded,
                room_code,
                user_id,
                result.stop_reason,
            )
            return result
        finally:
            session.close()

    def _get_deck(self, db: Session, room_code: str, lock: bool = False) -> Optional[RoomDeck]:
        stmt = select(RoomDeck).where(RoomDeck.room_code == room_code)
        if lock:
            stmt = stmt.with_for_update()
        return db.execute(stmt).scalar_one_or_none()

    def _get_position(
        self,
        db: Session,
        user_id: UUID,
        room_code: str,
        lock: bool = False,
    ) -> Optional[RoomDeckPosition]:
        stmt = select(RoomDeckPosition).where(
            and_(
                RoomDeckPosition.user_id == user_id,
                RoomDeckPosition.room_code == room_code,
            )
        )
        if lock:
            stmt = stmt.with_for_update()
        return db.execute(stmt).scalar_one_or_none()

    def _random_movie(self, db: Session, exclude: Optional[Set[UUID]] = None) -> Optional[Movie]:
        """Случайный фильм из базы (fallback после исчерпания каталога).

        Исключает уже просвайпанные участником фильмы (design.md, Decision 3),
        если после исключения остаётся хотя бы один вариант; иначе исключение
        снимается — иначе фид оборвался бы вместо допустимого повтора.
        """
        stmt = select(Movie).order_by(func.random()).limit(1)
        if exclude:
            movie = db.execute(stmt.where(Movie.id.not_in(list(exclude)))).scalar_one_or_none()
            if movie is not None:
                return movie
        return db.execute(stmt).scalar_one_or_none()

    def _swiped_movie_ids(self, db: Session, user: User, room: Room) -> Set[UUID]:
        """movie_id свайпов пользователя в этой комнате в текущей сессии."""
        session_start = get_session_start(db, room.participants, room.id)
        if session_start is None:
            return set()
        stmt = select(UserSwipe.movie_id).where(
            and_(
                UserSwipe.user_id == user.id,
                cast(UserSwipe.group_participants, JSONB).op("@>")(room.participants),
                UserSwipe.swiped_at >= session_start,
            )
        )
        return set(db.execute(stmt).scalars())

    def _swiped_movie_ids_in_room(self, db: Session, room: Room) -> Set[UUID]:
        """movie_id свайпов любого участника в этой комнате в текущей сессии."""
        session_start = get_session_start(db, room.participants, room.id)
        if session_start is None:
            return set()
        stmt = select(UserSwipe.movie_id).where(
            and_(
                cast(UserSwipe.group_participants, JSONB).op("@>")(room.participants),
                UserSwipe.swiped_at >= session_start,
            )
        )
        return set(db.execute(stmt).scalars())

    def _sample_movie_ids(self, db: Session, exclude: Set[UUID], limit: Optional[int] = None) -> list[str]:
        """Перемешанная пачка случайных movie_id из базы, исключая переданные."""
        if limit is None:
            limit = DECK_BATCH_SIZE
        stmt = select(Movie.id).order_by(func.random()).limit(limit)
        if exclude:
            stmt = stmt.where(Movie.id.not_in(list(exclude)))
        return [str(movie_id) for movie_id in db.execute(stmt).scalars()]


deck_service = DeckService()
