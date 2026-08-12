"""Сервис общего колода фильмов комнаты.

Каждая комната имеет один упорядоченный колод фильмов (таблица room_decks).
Участники движутся по нему независимо: у каждого своя позиция-курсор
(таблица room_deck_positions), которую продвигает каждый запрос «следующего
фильма». Поэтому параллельные запросы одного участника (предзагрузка фронта)
возвращают разные фильмы без повторов, а последовательность колода общая —
матч между участниками достижим.

Алгоритм выдачи (design.md, D3): prune → clamp → scan → advance.
"""
from datetime import datetime, timezone
from typing import Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import and_, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models.movie import Movie
from app.models.room import Room
from app.models.room_deck import RoomDeck
from app.models.room_deck_position import RoomDeckPosition
from app.models.swipe import UserSwipe
from app.models.user import User
from app.services.room_service import room_service

# Размер пачки при создании/пополнении колода (см. design.md, N=50).
DECK_BATCH_SIZE = 50


class DeckService:
    """Управление общим колодом фильмов комнаты."""

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

        movie, index = self._next_available(db, deck, position.position, swiped)
        if movie is None:
            # Дошли до конца колода — пополняем и продолжаем scan (D3, шаг 5).
            self._replenish_deck(db, deck, room, user)
            movie, index = self._next_available(db, deck, position.position, swiped)
            if movie is None:
                # Каталог исчерпан для участника (просвайпан весь доступный набор):
                # после полного круга отдаём случайный фильм повторно, чтобы фид
                # не заканчивался 404.
                return self._random_movie(db)

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

    def _replenish_deck(self, db: Session, deck: RoomDeck, room: Room, user: User) -> None:
        """Пополняет колод новой пачкой, блокируя строку на время записи.

        Исключаются только свайпы текущего участника (как и при scan) — фильмы,
        которые свайпнули другие участники, не блокируют пополнение, иначе
        свайпы из других комнат (подбор по составу участников) выжимают каталог.

        Коммит здесь не выполняется (design.md, D2): транзакционная граница —
        за внешним `get_next_movie_for_room`, чтобы персист позиции и пополнение
        колода не разрывались промежуточным commit.
        """
        locked = self._get_deck(db, deck.room_code, lock=True)
        if locked is None:
            raise RuntimeError(f"Deck for room {deck.room_code} disappeared")
        deck = locked

        exclude = self._swiped_movie_ids(db, user, room) | set(deck.movie_ids)
        new_ids = self._sample_movie_ids(db, exclude=exclude)
        if not new_ids:
            return

        deck.movie_ids = deck.movie_ids + new_ids
        logger.info("Replenished deck for room %s with %d movies", deck.room_code, len(new_ids))

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

    def _random_movie(self, db: Session) -> Optional[Movie]:
        """Случайный фильм из базы (fallback после исчерпания каталога)."""
        return db.execute(select(Movie).order_by(func.random()).limit(1)).scalar_one_or_none()

    def _swiped_movie_ids(self, db: Session, user: User, room: Room) -> Set[UUID]:
        """movie_id свайпов пользователя в этой комнате."""
        stmt = select(UserSwipe.movie_id).where(
            and_(
                UserSwipe.user_id == user.id,
                cast(UserSwipe.group_participants, JSONB).op("@>")(room.participants),
            )
        )
        return set(db.execute(stmt).scalars())

    def _swiped_movie_ids_in_room(self, db: Session, room: Room) -> Set[UUID]:
        """movie_id свайпов любого участника в этой комнате."""
        stmt = select(UserSwipe.movie_id).where(
            cast(UserSwipe.group_participants, JSONB).op("@>")(room.participants)
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
