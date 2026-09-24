import os
from pathlib import Path

# Переключаем приложение на тестовую БД ДО импорта app-модулей:
# engine/сессии и settings читают DATABASE_URL на этапе импорта.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://lotreamaun@localhost:5432/tinder_movie_test",
)
# Без токена уведомления о матче не отправляются, но матч создаётся.
os.environ["TELEGRAM_BOT_TOKEN"] = ""

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal, engine

# Импортируем приложение, чтобы маршруты/сервисы были доступны.
from app.main import app  # noqa: E402
from app.models import Room, RoomDeck  # noqa: F401
from app.models.match import Match  # noqa: F401
from app.models.movie import Movie  # noqa: F401
from app.models.swipe import UserSwipe  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.movie_service import movie_service
from app.services.room_service import room_service
from app.services.user_service import user_service

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _upgrade_schema() -> None:
    """Накатывает реальные Alembic-миграции на тестовую БД (схема == прод-схема)."""
    cfg = Config(str(_REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_REPO_ROOT / "backend" / "app" / "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def schema():
    _upgrade_schema()
    yield


@pytest.fixture()
def db(schema):
    """Чистая БД (схема из миграций) и сессия для каждого теста."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE users, movies, matches, user_swipes, room_decks, rooms CASCADE"
            )
        )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "TRUNCATE TABLE users, movies, matches, user_swipes, room_decks, rooms CASCADE"
                )
            )


@pytest.fixture(autouse=True)
def no_background_catalog_growth(monkeypatch):
    """Отключает фоновую догрузку каталога (реальные запросы к Kinopoisk).

    В тестовом каталоге всегда меньше `DECK_CATALOG_LOW_THRESHOLD` фильмов,
    поэтому иначе каждый запрос запускал бы поток. Тесты догрузки включают её
    обратно через `monkeypatch.delattr(deck_service, "_start_background_growth")`.

    Также сбрасывает паузу после пустой/неудачной догрузки (design.md
    fix-movie-catalog-exhaustion, Decision 8): `deck_service` — синглтон
    процесса, и без сброса пауза, поставленная одним тестом, блокировала бы
    догрузку в следующем.
    """
    from app.services.deck_service import deck_service

    monkeypatch.setattr(deck_service, "_start_background_growth", lambda user_id, room_code: False)
    deck_service._growth_cooldown_until = None
    yield
    deck_service._growth_cooldown_until = None


@pytest.fixture(autouse=True)
def reset_catalog_growth_cursor():
    """Сбрасывает курсор прохода по подборкам (design.md fix-catalog-growth-ceiling,
    Decision 3): `movie_service` — синглтон процесса, без сброса курсор,
    сдвинутый одним тестом, влиял бы на следующий.
    """
    movie_service._collection_index = 0
    movie_service._next_page = 1
    movie_service._new_in_pass = 0
    yield
    movie_service._collection_index = 0
    movie_service._next_page = 1
    movie_service._new_in_pass = 0


@pytest.fixture()
def client(db):
    """HTTP-клиент к приложению (работает на той же тестовой БД)."""
    return TestClient(app)


@pytest.fixture()
def make_user(db):
    def _make(telegram_id: int, first_name: str = "User") -> User:
        user = user_service.get_user_by_telegram_id(db, telegram_id)
        if not user:
            user = user_service.create_user(db, telegram_id=telegram_id, first_name=first_name)
        return user

    return _make


@pytest.fixture()
def make_movie(db):
    counter = {"n": 0}

    def _make() -> Movie:
        counter["n"] += 1
        n = counter["n"]
        return movie_service.create_movie(
            db,
            kinopoisk_id=1000 + n,
            title=f"Movie {n}",
            year=2020 + (n % 10),
            genre="Drama",
            poster_url="",
        )

    return _make


@pytest.fixture()
def make_room(db):
    def _make(creator: User, participant_ids: list[int]) -> Room:
        room = Room(
            id=room_service.generate_room_code(),
            creator_id=str(creator.id),
            participants=participant_ids,
        )
        db.add(room)
        db.commit()
        db.refresh(room)
        return room

    return _make
