"""Сервис общего колода фильмов комнаты.

Каждая комната имеет один упорядоченный колод фильмов (таблица room_decks).
Участники движутся по нему независимо: «следующий фильм» — первый id колода,
который существует в базе и ещё не свайпнут участником в этой комнате.
При исчерпании колод пополняется новой пачкой фильмов.
"""
from typing import Optional, Set

from sqlalchemy import and_, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID

from app.logging_config import logger
from app.models.movie import Movie
from app.models.room import Room
from app.models.room_deck import RoomDeck
from app.models.swipe import UserSwipe
from app.models.user import User
from app.services.room_service import room_service

# Размер пачки при создании/пополнении колода (см. design.md, N=50).
DECK_BATCH_SIZE = 50


class DeckService:
    """Управление общим колодом фильмов комнаты."""

    def get_next_movie_for_room(self, db: Session, user: User, room_code: str) -> Optional[Movie]:
        """Возвращает следующий непросвайпанный фильм общего колода комнаты.

        Если колода нет — создаёт его; если колод исчерпан — пополняет.
        Возвращает None, если фильм не найден.
        """
        room = room_service.get_room_by_code(db, room_code)
        if not room or user.telegram_id not in room.participants:
            return None

        deck = self._get_or_create_deck(db, room)
        swiped = self._swiped_movie_ids(db, user, room)

        movie = self._first_available_in_deck(db, deck, swiped)
        if movie:
            return movie

        self._replenish_deck(db, deck, room)
        return self._first_available_in_deck(db, deck, swiped)

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

    def _replenish_deck(self, db: Session, deck: RoomDeck, room: Room) -> None:
        """Пополняет колод новой пачкой, блокируя строку на время записи."""
        locked = self._get_deck(db, deck.room_code, lock=True)
        if locked is None:
            raise RuntimeError(f"Deck for room {deck.room_code} disappeared")
        deck = locked

        exclude = self._swiped_movie_ids_in_room(db, room) | set(deck.movie_ids)
        new_ids = self._sample_movie_ids(db, exclude=exclude)
        if not new_ids:
            return

        deck.movie_ids = deck.movie_ids + new_ids
        db.commit()
        logger.info("Replenished deck for room %s with %d movies", deck.room_code, len(new_ids))

    def _get_deck(self, db: Session, room_code: str, lock: bool = False) -> Optional[RoomDeck]:
        stmt = select(RoomDeck).where(RoomDeck.room_code == room_code)
        if lock:
            stmt = stmt.with_for_update()
        return db.execute(stmt).scalar_one_or_none()

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

    def _first_available_in_deck(self, db: Session, deck: RoomDeck, swiped: Set[UUID]) -> Optional[Movie]:
        """Первый существующий фильм колода, не свайпнутый участником.

        Удалённые фильмы (ротация) пропускаются и вычищаются из колода.
        """
        ids = [UUID(movie_id) for movie_id in deck.movie_ids]
        if not ids:
            return None

        existing_ids = set(db.execute(select(Movie.id).where(Movie.id.in_(ids))).scalars())

        pruned = [str(movie_id) for movie_id in ids if movie_id in existing_ids]
        if len(pruned) != len(deck.movie_ids):
            deck.movie_ids = pruned
            db.commit()

        for movie_id_str in pruned:
            movie_id = UUID(movie_id_str)
            if movie_id not in swiped:
                return db.get(Movie, movie_id)
        return None


deck_service = DeckService()
