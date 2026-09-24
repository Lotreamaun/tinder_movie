"""Тесты общего колода фильмов комнаты (change shared-deck)."""
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models.room_deck import RoomDeck
from app.models.swipe import UserSwipe
from app.services import deck_service as deck_service_module
from app.services import movie_service as movie_service_module
from app.services.deck_service import deck_service
from app.services.match_service import match_service
from app.services.movie_service import movie_service, LoadBatchResult
from app.services.swipe_service import swipe_service
from app.services.room_session import get_session_start
from app.services.user_service import user_service


def _deck_order(db, room_code: str) -> list[str]:
    deck = db.get(RoomDeck, room_code)
    return deck.movie_ids if deck else []


def _swipe(db, user, movie_id: UUID, room) -> None:
    swipe_service.create_swipe(
        db=db,
        user_id=str(user.id),
        movie_id=str(movie_id),
        swipe_type="like",
        group_participants=room.participants,
    )


def _wait_growth_idle() -> None:
    """Ждёт завершения фоновой догрузки (снятия guard)."""
    assert deck_service._growth_lock.acquire(timeout=5), "Фоновая догрузка не завершилась"
    deck_service._growth_lock.release()


def _set_swiped_at(db, user, movie_id: UUID, hours_ago: float) -> None:
    """Сдвигает время свайпа участника в прошлое."""
    swipe = db.execute(
        select(UserSwipe).where(UserSwipe.user_id == user.id, UserSwipe.movie_id == movie_id)
    ).scalar_one()
    swipe.swiped_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    db.commit()


# ---------------------------------------------------------------------------
# 5.1 — участники комнаты получают фильмы из одной общей последовательности
# ---------------------------------------------------------------------------
def test_participants_see_same_deck(db, make_user, make_movie, make_room):
    u1 = make_user(1001)
    u2 = make_user(1002)
    room = make_room(u1, [1001, 1002])
    for _ in range(5):
        make_movie()

    m1 = deck_service.get_next_movie_for_room(db, u1, room.id)
    m2 = deck_service.get_next_movie_for_room(db, u2, room.id)

    assert m1 is not None and m2 is not None
    # Оба участника видят один и тот же первый фильм общего колода.
    assert m1.id == m2.id
    assert _deck_order(db, room.id)


# ---------------------------------------------------------------------------
# 5.2 — без повторов для участника
# ---------------------------------------------------------------------------
def test_no_repeats_for_participant(db, make_user, make_movie, make_room):
    u1 = make_user(1003)
    u2 = make_user(1004)
    room = make_room(u1, [1003, 1004])
    for _ in range(5):
        make_movie()

    first = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert first is not None

    seen = {str(first.id)}
    _swipe(db, u1, first.id, room)

    order = _deck_order(db, room.id)
    assert len(order) >= 3

    for _ in range(len(order) - 1):
        movie = deck_service.get_next_movie_for_room(db, u1, room.id)
        assert movie is not None
        assert str(movie.id) not in seen
        seen.add(str(movie.id))
        _swipe(db, u1, movie.id, room)


# ---------------------------------------------------------------------------
# 5.3 — пополнение при исчерпании без уже свайпнутых фильмов
# ---------------------------------------------------------------------------
def test_deck_replenished_without_swiped(db, make_user, make_movie, make_room, monkeypatch):
    monkeypatch.setattr(deck_service_module, "DECK_BATCH_SIZE", 3)
    u1 = make_user(1005)
    u2 = make_user(1006)
    room = make_room(u1, [1005, 1006])
    for _ in range(6):
        make_movie()

    first_round = []
    for _ in range(3):
        movie = deck_service.get_next_movie_for_room(db, u1, room.id)
        assert movie is not None
        first_round.append(str(movie.id))
        _swipe(db, u1, movie.id, room)

    # Колод исчерпан — следующий запрос триггерит пополнение
    movie = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert movie is not None

    order = _deck_order(db, room.id)
    assert len(order) == 6

    # Первые 3 — исходный колод; пополнение не содержит уже свайпнутых фильмов
    replenished = order[3:]
    assert all(movie_id not in first_round for movie_id in replenished)
    # И не содержит дублей
    assert len(set(replenished)) == len(replenished)


# ---------------------------------------------------------------------------
# 5.4 — пропуск удалённых фильмов колода (устойчивость к ротации)
# ---------------------------------------------------------------------------
def test_missing_movie_skipped(db, make_user, make_movie, make_room):
    u1 = make_user(1007)
    u2 = make_user(1008)
    room = make_room(u1, [1007, 1008])
    movies = [make_movie() for _ in range(3)]

    first = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert first is not None

    order = _deck_order(db, room.id)
    first_deck_id = order[0]

    # Удаляем фильм, который стоит первым в колоде
    victim = next(m for m in movies if str(m.id) == first_deck_id)
    movie_service.delete_movie(db, victim)

    next_movie = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert next_movie is not None
    assert str(next_movie.id) != first_deck_id

    # Удалённый фильм вычищен из колода
    assert first_deck_id not in _deck_order(db, room.id)


# ---------------------------------------------------------------------------
# 5.5 — матч достижим: все участники комнаты лайкнули фильм общего колода
# ---------------------------------------------------------------------------
def test_match_created_when_all_like_deck_movie(client, db, make_user, make_movie, make_room):
    u1 = make_user(1009)
    make_user(1010)
    room = make_room(u1, [1009, 1010])

    for _ in range(5):
        make_movie()

    r1 = client.get("/api/movies/random", headers={"telegram-id": "1009"}, params={"room_code": room.id})
    assert r1.status_code == 200
    movie1 = r1.json()["data"]["id"]

    r2 = client.get("/api/movies/random", headers={"telegram-id": "1010"}, params={"room_code": room.id})
    assert r2.status_code == 200
    movie2 = r2.json()["data"]["id"]

    # Оба участника видят один и тот же первый фильм общего колода.
    assert movie1 == movie2

    body = {"movie_id": movie1, "swipe_type": "like", "group_participants": [1009, 1010]}
    for tg in ("1009", "1010"):
        resp = client.post("/api/swipes/", json=body, headers={"telegram-id": tg})
        assert resp.status_code == 200

    matches = client.get("/api/matches/group", params={"participants": "1009,1010"})
    assert matches.status_code == 200
    assert len(matches.json()["data"]) >= 1


# ---------------------------------------------------------------------------
# 5.6 — вне комнаты поведение прежнее (случайный фильм)
# ---------------------------------------------------------------------------
def test_outside_room_random_movie(client, db, make_movie):
    for _ in range(3):
        make_movie()

    resp = client.get("/api/movies/random")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["id"]


def test_extra_cache_buster_param_is_ignored(client, db, make_user, make_movie, make_room):
    """Одноразовый параметр `_` фронта (антисклейка запросов в WebKit) бэкенд игнорирует."""
    u1 = make_user(1013)
    make_user(1014)
    room = make_room(u1, [1013, 1014])
    for _ in range(3):
        make_movie()

    resp = client.get(
        "/api/movies/random",
        headers={"telegram-id": "1013"},
        params={"room_code": room.id, "_": "123"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"]
    # Эндпоинт по своей природе некэшируем: каждый вызов продвигает курсор участника
    assert resp.headers["cache-control"] == "no-store"


def test_room_code_requires_identity_and_membership(client, db, make_user, make_movie, make_room):
    u1 = make_user(1011)
    make_user(1012)
    room = make_room(u1, [1011])
    for _ in range(3):
        make_movie()

    # telegram_id обязателен, если передан room_code
    resp_no_header = client.get("/api/movies/random", params={"room_code": room.id})
    assert resp_no_header.status_code == 400

    # Пользователь вне комнаты получает 400
    resp_not_member = client.get(
        "/api/movies/random",
        headers={"telegram-id": "1012"},
        params={"room_code": room.id},
    )
    assert resp_not_member.status_code == 400

    # Участник комнаты получает фильм из общего колода
    resp_member = client.get(
        "/api/movies/random",
        headers={"telegram-id": "1011"},
        params={"room_code": room.id},
    )
    assert resp_member.status_code == 200


# ---------------------------------------------------------------------------
# 6. fix-swipe-deck: курсор позиции участника в колоде
# ---------------------------------------------------------------------------
# 6.1 — каждый запрос продвигает позицию: разные фильмы подряд, без свайпов
def test_cursor_advances_without_swipes(db, make_user, make_movie, make_room):
    u1 = make_user(1101)
    u2 = make_user(1102)
    room = make_room(u1, [1101, 1102])
    for _ in range(5):
        make_movie()

    seen = []
    for _ in range(5):
        movie = deck_service.get_next_movie_for_room(db, u1, room.id)
        assert movie is not None
        seen.append(str(movie.id))

    # Курсор продвигается даже без свайпов — повторов нет,
    # порядок совпадает с порядком общего колода.
    assert len(set(seen)) == 5
    assert seen == _deck_order(db, room.id)


# 6.2 — 5 последовательных запросов (как параллельные предзагрузки с
# отдельными сессиями) возвращают 5 разных фильмов
def test_prefetch_requests_return_distinct_movies(db, make_user, make_movie, make_room):
    u1 = make_user(1103)
    u2 = make_user(1104)
    room = make_room(u1, [1103, 1104])
    for _ in range(10):
        make_movie()

    results = []
    for _ in range(5):
        session = SessionLocal()
        try:
            fresh_user = user_service.get_user_by_telegram_id(session, 1103)
            movie = deck_service.get_next_movie_for_room(session, fresh_user, room.id)
            results.append(str(movie.id) if movie else None)
        finally:
            session.close()

    assert all(results)
    assert len(set(results)) == 5


# 6.3 — просвайпанный фильм пропускается при сканировании
def test_cursor_skips_swiped_movie(db, make_user, make_movie, make_room):
    u1 = make_user(1105)
    u2 = make_user(1106)
    room = make_room(u1, [1105, 1106])
    for _ in range(5):
        make_movie()

    # Первый запрос выдаёт фильм и продвигает позицию до 1
    deck_service.get_next_movie_for_room(db, u1, room.id)
    order = _deck_order(db, room.id)

    # Свайпаем следующий фильм колода (индекс 1)
    _swipe(db, u1, UUID(order[1]), room)

    # Следующий запрос пропускает просвайпанный и выдаёт фильм с индекса 2
    movie = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert movie is not None
    assert str(movie.id) == order[2]


# 6.4 — удалённый фильм (ротация) пропускается и вычищается, без повторов
def test_cursor_skips_deleted_movie(db, make_user, make_movie, make_room):
    u1 = make_user(1107)
    u2 = make_user(1108)
    room = make_room(u1, [1107, 1108])
    movies = [make_movie() for _ in range(5)]

    first = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert first is not None
    order = _deck_order(db, room.id)

    # Удаляем фильм, который стоит вторым в колоде (индекс 1)
    victim = next(m for m in movies if str(m.id) == order[1])
    movie_service.delete_movie(db, victim)

    # Следующий запрос пропускает удалённый фильм и выдаёт третий
    next_movie = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert next_movie is not None
    assert str(next_movie.id) == order[2]

    # Удалённый фильм вычищен из колода
    assert order[1] not in _deck_order(db, room.id)


# 6.5 — позиции участников независимы
def test_positions_independent_between_participants(db, make_user, make_movie, make_room):
    u1 = make_user(1109)
    u2 = make_user(1110)
    room = make_room(u1, [1109, 1110])
    for _ in range(10):
        make_movie()

    # u1 продвигается на 3 фильма вперёд
    first_three = [
        deck_service.get_next_movie_for_room(db, u1, room.id) for _ in range(3)
    ]
    assert all(m is not None for m in first_three)

    # u2 начинает с позиции 0 — первый фильм тот же, что был первым у u1
    m2 = deck_service.get_next_movie_for_room(db, u2, room.id)
    assert m2 is not None
    assert str(m2.id) == str(first_three[0].id)

    # Продвижение u2 не влияет на u1: следующий фильм u1 — четвёртый в колоде
    order = _deck_order(db, room.id)
    m1_next = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert m1_next is not None
    assert str(m1_next.id) == order[3]


# 6.6 — позиция продолжает движение после пополнения колода
def test_cursor_resumes_after_replenish(db, make_user, make_movie, make_room, monkeypatch):
    monkeypatch.setattr(deck_service_module, "DECK_BATCH_SIZE", 3)
    u1 = make_user(1111)
    u2 = make_user(1112)
    room = make_room(u1, [1111, 1112])
    for _ in range(6):
        make_movie()

    first_round = [
        deck_service.get_next_movie_for_room(db, u1, room.id) for _ in range(3)
    ]
    assert all(m is not None for m in first_round)

    # Колод исчерпан — следующий запрос пополняет и продолжает scan
    fourth = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert fourth is not None
    assert str(fourth.id) not in {str(m.id) for m in first_round}

    assert len(_deck_order(db, room.id)) == 6


# 6.7 — свайпы других участников не блокируют пополнение колода
def test_replenish_not_blocked_by_other_participant_swipes(db, make_user, make_movie, make_room, monkeypatch):
    monkeypatch.setattr(deck_service_module, "DECK_BATCH_SIZE", 3)
    u1 = make_user(1113)
    u2 = make_user(1114)
    room = make_room(u1, [1113, 1114])
    for _ in range(6):
        make_movie()

    # u1 исчерпывает колод
    for _ in range(3):
        movie = deck_service.get_next_movie_for_room(db, u1, room.id)
        assert movie is not None
        _swipe(db, u1, movie.id, room)

    order = _deck_order(db, room.id)
    # u2 свайпает оставшиеся фильмы каталога — это не должно мешать пополнению для u1
    others = [m.id for m in movie_service.list_movies(db) if str(m.id) not in order]
    for movie_id in others:
        _swipe(db, u2, movie_id, room)

    movie = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert movie is not None


# 6.8 — каталог исчерпан: вместо None возвращается случайный фильм (повтор)
def test_fallback_random_movie_when_catalog_exhausted(db, make_user, make_movie, make_room, monkeypatch):
    monkeypatch.setattr(deck_service_module, "DECK_BATCH_SIZE", 3)
    u1 = make_user(1115)
    u2 = make_user(1116)
    room = make_room(u1, [1115, 1116])
    for _ in range(3):
        make_movie()

    # u1 свайпает все 3 фильма каталога
    for _ in range(3):
        movie = deck_service.get_next_movie_for_room(db, u1, room.id)
        assert movie is not None
        _swipe(db, u1, movie.id, room)

    # Каталог исчерпан, фоновая догрузка (отключена в conftest) новых фильмов
    # не дала: запрос сразу возвращает фильм (повтор), а не None
    movie = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert movie is not None


# ---------------------------------------------------------------------------
# 8.1 — остаток ниже порога: догрузка стартует в фоне, ответ её не ждёт;
# догруженный фильм приходит следующим запросам через пополнение колода
# ---------------------------------------------------------------------------
def test_background_growth_does_not_block_response(db, make_user, make_movie, make_room, monkeypatch):
    monkeypatch.delattr(deck_service, "_start_background_growth")
    monkeypatch.setattr(deck_service_module, "DECK_BATCH_SIZE", 3)
    u1 = make_user(1201)
    make_user(1202)
    room = make_room(u1, [1201, 1202])
    for _ in range(3):
        make_movie()

    release = threading.Event()
    grown_ids: list[str] = []

    def slow_load_batch_movies(session, count=10):
        # Имитация долгой догрузки из Kinopoisk; второй и последующие вызовы
        # (новые пересечения порога) ничего не добавляют.
        release.wait(timeout=5)
        if grown_ids:
            return LoadBatchResult(loaded=0, stop_reason="budget")
        movie = movie_service.create_movie(
            session, kinopoisk_id=900001, title="Grown Movie", year=2024, genre="Drama", poster_url=""
        )
        grown_ids.append(str(movie.id))
        return LoadBatchResult(loaded=1, stop_reason="count")

    monkeypatch.setattr(movie_service, "load_batch_movies", slow_load_batch_movies)

    try:
        started = time.monotonic()
        movie = deck_service.get_next_movie_for_room(db, u1, room.id)
        elapsed = time.monotonic() - started
        assert movie is not None
        assert elapsed < 1, f"Ответ ждал фоновую догрузку: {elapsed:.2f}с"
        assert deck_service._growth_lock.locked(), "Фоновая догрузка должна была стартовать"

        seen = {str(movie.id)}
        _swipe(db, u1, movie.id, room)
        for _ in range(2):
            movie = deck_service.get_next_movie_for_room(db, u1, room.id)
            seen.add(str(movie.id))
            _swipe(db, u1, movie.id, room)
    finally:
        release.set()
        _wait_growth_idle()

    # Догрузка завершилась — исчерпавший каталог участник получает новый
    # фильм через обычное пополнение колода (replenished-from-catalog).
    movie = deck_service.get_next_movie_for_room(db, u1, room.id)
    _wait_growth_idle()
    assert movie is not None
    assert str(movie.id) == grown_ids[0]
    assert str(movie.id) not in seen


# ---------------------------------------------------------------------------
# 8.2 — пока догрузка идёт, повторные пересечения порога не запускают вторую
# ---------------------------------------------------------------------------
def test_background_growth_guard_prevents_parallel_runs(db, make_user, make_movie, make_room, monkeypatch):
    monkeypatch.delattr(deck_service, "_start_background_growth")
    u1 = make_user(1203)
    u2 = make_user(1204)
    room = make_room(u1, [1203, 1204])
    for _ in range(5):
        make_movie()

    release = threading.Event()
    calls = {"n": 0}

    def slow_load_batch_movies(session, count=10):
        calls["n"] += 1
        release.wait(timeout=5)
        return LoadBatchResult(loaded=0, stop_reason="budget")

    monkeypatch.setattr(movie_service, "load_batch_movies", slow_load_batch_movies)

    try:
        for user in (u1, u2, u1, u2):
            assert deck_service.get_next_movie_for_room(db, user, room.id) is not None
        assert calls["n"] == 1
    finally:
        release.set()
        _wait_growth_idle()


# ---------------------------------------------------------------------------
# 4.2 — fallback без повтора: _random_movie исключает переданные id, пока
# есть альтернатива, и снимает исключение, если альтернативы не осталось
# ---------------------------------------------------------------------------
def test_random_movie_excludes_swiped_when_alternative_exists(db, make_movie):
    m1 = make_movie()
    m2 = make_movie()
    m3 = make_movie()

    result = deck_service._random_movie(db, exclude={m1.id, m2.id})
    assert result is not None
    assert result.id == m3.id


def test_random_movie_falls_back_to_repeat_when_no_alternative(db, make_movie):
    m1 = make_movie()

    # Единственный фильм в каталоге тоже в exclude — исключение снимается,
    # иначе фид оборвался бы вместо допустимого повтора.
    result = deck_service._random_movie(db, exclude={m1.id})
    assert result is not None
    assert result.id == m1.id


# ---------------------------------------------------------------------------
# 4.3 — _grow_catalog работает на отдельной сессии и не требует/не держит
# FOR UPDATE текущей (внешней) транзакции деки
# ---------------------------------------------------------------------------
def test_grow_catalog_does_not_contend_with_deck_lock(make_user, make_room, monkeypatch):
    u1 = make_user(1206)
    room = make_room(u1, [1206])

    # Отдельная "внешняя" сессия, имитирующая основную транзакцию
    # get_next_movie_for_room, которая держит FOR UPDATE на deck комнаты.
    outer_session = SessionLocal()
    try:
        deck = RoomDeck(room_code=room.id, movie_ids=[])
        outer_session.add(deck)
        outer_session.commit()

        locked = outer_session.execute(
            select(RoomDeck).where(RoomDeck.room_code == room.id).with_for_update()
        ).scalar_one()
        assert locked is not None

        def fake_load_batch_movies(session, count=10):
            movie_service.create_movie(
                session,
                kinopoisk_id=900002,
                title="Grown While Locked",
                year=2024,
                genre="Drama",
                poster_url="",
            )
            return LoadBatchResult(loaded=1, stop_reason="count")

        monkeypatch.setattr(movie_service, "load_batch_movies", fake_load_batch_movies)

        # _grow_catalog открывает свою SessionLocal() и не трогает room_decks —
        # вызов не блокируется удержанным FOR UPDATE внешней сессии.
        grown = deck_service._grow_catalog(u1.id, room.id)
        assert grown.loaded == 1
    finally:
        outer_session.rollback()
        outer_session.close()


# 6.9 — параллельный первый запрос (позиция ещё не создана) возвращает
# разные фильмы (гонка create-commit vs advance, change fix-parallel-preload-duplicates)
def test_parallel_first_requests_return_distinct_movies(db, make_user, make_movie, make_room):
    u1 = make_user(1117)
    u2 = make_user(1118)
    room = make_room(u1, [1117, 1118])
    for _ in range(10):
        make_movie()

    n = 5
    barrier = threading.Barrier(n)
    results = {}
    errors = {}

    def worker(idx: int) -> None:
        try:
            session = SessionLocal()
            try:
                fresh_user = user_service.get_user_by_telegram_id(session, 1117)
                # Синхронизируем потоки непосредственно перед запросом,
                # чтобы все вошли в get_next_movie_for_room «почти одновременно».
                barrier.wait(timeout=15)
                movie = deck_service.get_next_movie_for_room(session, fresh_user, room.id)
                results[idx] = str(movie.id) if movie else None
            finally:
                session.close()
        except Exception as e:  # noqa: BLE001
            errors[idx] = repr(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Thread errors: {errors}"
    movie_ids = [results[i] for i in range(n)]
    assert all(movie_ids), f"Some requests returned None: {movie_ids}"
    assert len(set(movie_ids)) == n, f"Duplicates in parallel first requests: {movie_ids}"


# ---------------------------------------------------------------------------
# 8.3 — свайпы старше 24ч без более поздних свайпов группы не исключают фильмы
# ---------------------------------------------------------------------------
def test_expired_session_swipes_not_excluded(db, make_user, make_movie, make_room):
    u1 = make_user(1301)
    make_user(1302)
    room = make_room(u1, [1301, 1302])
    movies = [make_movie() for _ in range(3)]
    for movie in movies:
        _swipe(db, u1, movie.id, room)

    assert deck_service._swiped_movie_ids(db, u1, room) == {m.id for m in movies}

    for movie in movies:
        _set_swiped_at(db, u1, movie.id, hours_ago=25)

    # Сессия истекла: прошлые свайпы не считаются показанными
    assert get_session_start(db, room.participants) is None
    assert deck_service._swiped_movie_ids(db, u1, room) == set()
    assert deck_service._swiped_movie_ids_in_room(db, room) == set()

    # Новый свайп начинает новую сессию, в которую старые не входят
    _swipe(db, u1, movies[0].id, room)
    assert deck_service._swiped_movie_ids(db, u1, room) == {movies[0].id}


# ---------------------------------------------------------------------------
# 8.4 — цепочка свайпов с разрывами < 24ч остаётся одной сессией
# ---------------------------------------------------------------------------
def test_session_chain_with_short_gaps_continues(db, make_user, make_movie, make_room):
    u1 = make_user(1303)
    u2 = make_user(1304)
    room = make_room(u1, [1303, 1304])
    movies = [make_movie() for _ in range(5)]

    # Разрыв 40ч (-100ч → -60ч) закрывает старую сессию; дальше разрывы
    # по 20ч — одна текущая сессия, начавшаяся 60ч назад.
    plan = [(u1, 100), (u2, 60), (u1, 40), (u2, 20), (u1, 1)]
    for movie, (user, hours_ago) in zip(movies, plan):
        _swipe(db, user, movie.id, room)
        _set_swiped_at(db, user, movie.id, hours_ago=hours_ago)

    session_start = get_session_start(db, room.participants)
    assert session_start is not None
    expected = datetime.now(timezone.utc) - timedelta(hours=60)
    assert abs((session_start - expected).total_seconds()) < 60

    assert deck_service._swiped_movie_ids(db, u1, room) == {movies[2].id, movies[4].id}
    assert deck_service._swiped_movie_ids_in_room(db, room) == {m.id for m in movies[1:]}


# ---------------------------------------------------------------------------
# 8.5 — матч засчитывает только лайки текущей сессии
# ---------------------------------------------------------------------------
def test_check_match_ignores_expired_session_likes(db, make_user, make_movie, make_room):
    u1 = make_user(1305)
    u2 = make_user(1306)
    room = make_room(u1, [1305, 1306])
    movie = make_movie()

    _swipe(db, u1, movie.id, room)
    _set_swiped_at(db, u1, movie.id, hours_ago=30)

    # Лайк u2 начинает новую сессию — лайк u1 остался в истёкшей
    _swipe(db, u2, movie.id, room)
    assert swipe_service.check_match(db, str(movie.id), room.participants) is False

    # Повторный лайк u1 переносит его в текущую сессию
    _swipe(db, u1, movie.id, room)
    assert swipe_service.check_match(db, str(movie.id), room.participants) is True


# ---------------------------------------------------------------------------
# 8.6 — истечение сессии не трогает уже созданные матчи
# ---------------------------------------------------------------------------
def test_session_expiry_keeps_existing_matches(db, make_user, make_movie, make_room):
    u1 = make_user(1307)
    u2 = make_user(1308)
    room = make_room(u1, [1307, 1308])
    movie = make_movie()

    for user in (u1, u2):
        _swipe(db, user, movie.id, room)
    assert swipe_service.check_match(db, str(movie.id), room.participants) is True
    match = match_service.create_match(db, str(movie.id), room.participants)

    for user in (u1, u2):
        _set_swiped_at(db, user, movie.id, hours_ago=25)

    assert swipe_service.check_match(db, str(movie.id), room.participants) is False
    assert deck_service.get_next_movie_for_room(db, u1, room.id) is not None

    matches = match_service.list_matches_for_group(db, room.participants)
    assert [m.id for m in matches] == [match.id]
    assert str(matches[0].movie_id) == str(movie.id)


# ---------------------------------------------------------------------------
# 10.2 — после истечения сессии старые фильмы возвращаются через рецикл в
# общий колод: участники получают их в одном порядке, матч достижим
# ---------------------------------------------------------------------------
def test_recycle_after_session_expiry_keeps_shared_order(db, make_user, make_movie, make_room, monkeypatch):
    monkeypatch.setattr(deck_service_module, "DECK_BATCH_SIZE", 3)
    u1 = make_user(1401)
    u2 = make_user(1402)
    room = make_room(u1, [1401, 1402])
    for _ in range(6):
        make_movie()

    # Оба участника проходят весь каталог (два пакета колода) и свайпают всё
    for user in (u1, u2):
        for _ in range(6):
            movie = deck_service.get_next_movie_for_room(db, user, room.id)
            _swipe(db, user, movie.id, room)
    assert len(_deck_order(db, room.id)) == 6

    for user in (u1, u2):
        for movie_id in _deck_order(db, room.id):
            _set_swiped_at(db, user, UUID(movie_id), hours_ago=25)

    m1 = deck_service.get_next_movie_for_room(db, u1, room.id)
    m2 = deck_service.get_next_movie_for_room(db, u2, room.id)
    assert m1 is not None and m2 is not None
    # Рецикл дописал в колод фильмы первого пакета (вне окна перед курсором)
    order = _deck_order(db, room.id)
    assert len(order) == 9
    assert set(order[6:]) == set(order[:3])
    # Общий порядок: оба участника получили один и тот же фильм — матч достижим
    assert m1.id == m2.id == UUID(order[6])
    _swipe(db, u1, m1.id, room)
    _swipe(db, u2, m2.id, room)
    assert swipe_service.check_match(db, str(m1.id), room.participants) is True


# ---------------------------------------------------------------------------
# 10.3 — рецикл не возвращает недавно выданные, но ещё не свайпнутые фильмы
# (очередь предзагрузки фронта)
# ---------------------------------------------------------------------------
def test_recycle_skips_recently_served_unswiped(db, make_user, make_movie, make_room, monkeypatch):
    monkeypatch.setattr(deck_service_module, "DECK_BATCH_SIZE", 3)
    u1 = make_user(1403)
    make_user(1404)
    room = make_room(u1, [1403, 1404])
    for _ in range(9):
        make_movie()

    served = [deck_service.get_next_movie_for_room(db, u1, room.id) for _ in range(9)]
    # 1–3: пропущены без свайпа давно; 4–6: свайпнуты; 7–9: в очереди клиента
    for movie in served[3:6]:
        _swipe(db, u1, movie.id, room)

    movie = deck_service.get_next_movie_for_room(db, u1, room.id)
    order = _deck_order(db, room.id)
    recycled = set(order[9:])
    assert recycled == {str(m.id) for m in served[:3]}
    assert str(movie.id) in recycled


# ---------------------------------------------------------------------------
# Заглушка httpx.Client для /films/collections (change fix-catalog-growth-ceiling)
# ---------------------------------------------------------------------------
class _FakeCollectionsResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeCollectionsClient:
    """Заглушка httpx.Client для `/films/collections`: карта (collection, page) → payload."""

    def __init__(self, pages: dict, calls: Optional[list] = None):
        self._pages = pages
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None, headers=None):
        key = (params["type"], params["page"])
        if self._calls is not None:
            self._calls.append(key)
        payload = self._pages.get(key, {"items": [], "totalPages": params["page"]})
        return _FakeCollectionsResponse(payload)


def _collection_item(kinopoisk_id: int, item_type: Optional[str] = "FILM") -> dict:
    item = {
        "kinopoiskId": kinopoisk_id,
        "nameRu": f"Movie {kinopoisk_id}",
        "year": 2024,
        "genres": [{"genre": "Drama"}],
        "posterUrl": "",
    }
    if item_type is not None:
        item["type"] = item_type
    return item


def _patch_collections(monkeypatch, pages: dict, calls: Optional[list] = None) -> None:
    monkeypatch.setattr(settings, "KINOPOISK_API_KEY", "test-key")
    monkeypatch.setattr(
        movie_service_module.httpx, "Client", lambda *a, **kw: _FakeCollectionsClient(pages, calls)
    )


# ---------------------------------------------------------------------------
# _fetch_collection_page — известные по kinopoisk_id и не-FILM элементы
# отсеиваются на уровне страницы (design.md, Decision 1/4)
# ---------------------------------------------------------------------------
def test_fetch_collection_page_skips_known_and_non_film(db, make_movie, monkeypatch):
    known = make_movie()
    items = [
        {"kinopoiskId": known.kinopoisk_id, "type": "FILM"},
        _collection_item(9500, "FILM"),
        _collection_item(9501, "TV_SERIES"),
    ]
    pages = {("TOP_250_MOVIES", 1): {"items": items, "totalPages": 4}}
    _patch_collections(monkeypatch, pages)

    page = movie_service._fetch_collection_page(db, "TOP_250_MOVIES", 1)

    assert page is not None
    assert [m["kinopoisk_id"] for m in page.items] == [9500]
    assert page.total_pages == 4
    assert page.raw_count == 3


# ---------------------------------------------------------------------------
# 5.2 — подборка длиннее 10 страниц: жёсткого потолка в 10 страниц нет,
# новые фильмы со страниц за пределами старого лимита загружаются
# ---------------------------------------------------------------------------
def test_load_batch_movies_goes_past_old_ten_page_limit(db, monkeypatch):
    monkeypatch.setattr(settings, "KINOPOISK_COLLECTIONS", ["TOP_250_MOVIES"])
    monkeypatch.setattr(settings, "CATALOG_GROWTH_MAX_PAGES", 15)

    known_ids = [2000 + i for i in range(10)]
    for kid in known_ids:
        movie_service.create_movie(db, kinopoisk_id=kid, title=f"Known {kid}", year=2020, genre="Drama", poster_url="")

    pages = {}
    for i, kid in enumerate(known_ids, start=1):
        pages[("TOP_250_MOVIES", i)] = {"items": [{"kinopoiskId": kid, "type": "FILM"}], "totalPages": 13}
    for page, kid in zip([11, 12, 13], [9001, 9002, 9003]):
        pages[("TOP_250_MOVIES", page)] = {"items": [_collection_item(kid)], "totalPages": 13}
    _patch_collections(monkeypatch, pages)

    result = movie_service.load_batch_movies(db, count=10)

    assert result.loaded == 3
    assert result.stop_reason == "pass_end"
    assert result.new_in_pass == 3
    for kid in (9001, 9002, 9003):
        assert movie_service.get_movie_by_kinopoisk_id(db, kid) is not None


# ---------------------------------------------------------------------------
# 5.3 — подборка исчерпана раньше последней в списке: догрузка переходит к
# следующей подборке в той же попытке
# ---------------------------------------------------------------------------
def test_load_batch_movies_moves_to_next_collection_in_same_attempt(db, monkeypatch):
    monkeypatch.setattr(settings, "KINOPOISK_COLLECTIONS", ["COLLECTION_A", "COLLECTION_B"])
    monkeypatch.setattr(settings, "CATALOG_GROWTH_MAX_PAGES", 15)
    pages = {
        ("COLLECTION_A", 1): {"items": [_collection_item(9100)], "totalPages": 1},
        ("COLLECTION_B", 1): {"items": [_collection_item(9101)], "totalPages": 1},
    }
    _patch_collections(monkeypatch, pages)

    result = movie_service.load_batch_movies(db, count=10)

    assert result.loaded == 2
    assert result.stop_reason == "pass_end"
    assert movie_service.get_movie_by_kinopoisk_id(db, 9100) is not None
    assert movie_service.get_movie_by_kinopoisk_id(db, 9101) is not None


# ---------------------------------------------------------------------------
# 5.4 — бюджет страниц исчерпан: следующая попытка продолжает со страницы,
# следующей за последней просмотренной, а не с начала
# ---------------------------------------------------------------------------
def test_load_batch_movies_resumes_after_budget_exhausted(db, monkeypatch):
    monkeypatch.setattr(settings, "KINOPOISK_COLLECTIONS", ["TOP_250_MOVIES"])
    monkeypatch.setattr(settings, "CATALOG_GROWTH_MAX_PAGES", 2)
    pages = {
        ("TOP_250_MOVIES", p): {"items": [_collection_item(9200 + p)], "totalPages": 5} for p in range(1, 6)
    }
    calls: list = []
    _patch_collections(monkeypatch, pages, calls)

    result1 = movie_service.load_batch_movies(db, count=10)
    assert result1.stop_reason == "budget"
    assert result1.loaded == 2
    assert calls == [("TOP_250_MOVIES", 1), ("TOP_250_MOVIES", 2)]

    result2 = movie_service.load_batch_movies(db, count=10)
    assert calls[2:] == [("TOP_250_MOVIES", 3), ("TOP_250_MOVIES", 4)]
    assert result2.stop_reason == "budget"
    assert result2.loaded == 2


# ---------------------------------------------------------------------------
# 5.5 — конец полного прохода: попытка останавливается на последней странице
# последней подборки, не начиная новый проход; следующий проход начинает с
# первой страницы первой подборки
# ---------------------------------------------------------------------------
def test_load_batch_movies_stops_at_pass_end_and_next_pass_restarts(db, monkeypatch):
    monkeypatch.setattr(settings, "KINOPOISK_COLLECTIONS", ["TOP_250_MOVIES"])
    monkeypatch.setattr(settings, "CATALOG_GROWTH_MAX_PAGES", 15)
    pages = {("TOP_250_MOVIES", 1): {"items": [_collection_item(9300)], "totalPages": 1}}
    calls: list = []
    _patch_collections(monkeypatch, pages, calls)

    result = movie_service.load_batch_movies(db, count=100)

    assert result.stop_reason == "pass_end"
    assert result.loaded == 1
    assert result.new_in_pass == 1
    assert calls == [("TOP_250_MOVIES", 1)]
    assert movie_service._collection_index == 0
    assert movie_service._next_page == 1

    calls.clear()
    movie_service.load_batch_movies(db, count=100)
    assert calls == [("TOP_250_MOVIES", 1)]


# ---------------------------------------------------------------------------
# 5.6 — new_in_pass суммируется по нескольким попыткам одного прохода и
# обнуляется на конце прохода
# ---------------------------------------------------------------------------
def test_new_in_pass_accumulates_and_resets_at_pass_end(db, monkeypatch):
    monkeypatch.setattr(settings, "KINOPOISK_COLLECTIONS", ["TOP_250_MOVIES"])
    monkeypatch.setattr(settings, "CATALOG_GROWTH_MAX_PAGES", 1)
    pages = {
        ("TOP_250_MOVIES", p): {"items": [_collection_item(9400 + p)], "totalPages": 3} for p in range(1, 4)
    }
    _patch_collections(monkeypatch, pages)

    r1 = movie_service.load_batch_movies(db, count=10)
    assert r1.stop_reason == "budget"
    assert movie_service._new_in_pass == 1

    r2 = movie_service.load_batch_movies(db, count=10)
    assert r2.stop_reason == "budget"
    assert movie_service._new_in_pass == 2

    r3 = movie_service.load_batch_movies(db, count=10)
    assert r3.stop_reason == "pass_end"
    assert r3.new_in_pass == 3
    assert movie_service._new_in_pass == 0


# ---------------------------------------------------------------------------
# 5.7 — сериалы (type != FILM) не попадают в каталог; для новых фильмов из
# подборки не делается отдельный запрос полных данных (design.md, Decision 1)
# ---------------------------------------------------------------------------
def test_load_batch_movies_filters_non_film_without_extra_full_data_request(db, monkeypatch):
    monkeypatch.setattr(settings, "KINOPOISK_COLLECTIONS", ["TOP_250_MOVIES"])
    items = [
        _collection_item(9500, "FILM"),
        _collection_item(9501, "TV_SERIES"),
        _collection_item(9502, item_type=None),  # нет type — принимается (совместимость)
    ]
    pages = {("TOP_250_MOVIES", 1): {"items": items, "totalPages": 1}}
    _patch_collections(monkeypatch, pages)

    full_data_calls: list = []
    monkeypatch.setattr(
        movie_service,
        "fetch_movie_from_kinopoisk",
        lambda *a, **kw: full_data_calls.append(a) or None,
    )

    result = movie_service.load_batch_movies(db, count=10)

    assert result.loaded == 2
    assert full_data_calls == []
    assert movie_service.get_movie_by_kinopoisk_id(db, 9500) is not None
    assert movie_service.get_movie_by_kinopoisk_id(db, 9501) is None
    assert movie_service.get_movie_by_kinopoisk_id(db, 9502) is not None


# ---------------------------------------------------------------------------
# 5.8 — пауза догрузки зависит от причины остановки попытки (design.md, Decision 6)
# ---------------------------------------------------------------------------
def test_growth_pause_budget_without_new_movies_sets_no_cooldown(db, make_user, make_room, monkeypatch):
    monkeypatch.delattr(deck_service, "_start_background_growth")
    u1 = make_user(1501)
    room = make_room(u1, [1501])

    monkeypatch.setattr(
        movie_service, "load_batch_movies", lambda session, count=10: LoadBatchResult(loaded=0, stop_reason="budget")
    )

    deck_service._growth_cooldown_until = None
    deck_service._maybe_grow_catalog(db, u1, room, set())
    _wait_growth_idle()
    assert deck_service._growth_cooldown_until is None


def test_growth_pause_error_is_short_and_blocks_retry_until_expiry(db, make_user, make_room, monkeypatch):
    monkeypatch.delattr(deck_service, "_start_background_growth")
    u1 = make_user(1502)
    room = make_room(u1, [1502])

    calls = {"n": 0}

    def failing_load_batch_movies(session, count=10):
        calls["n"] += 1
        return LoadBatchResult(loaded=0, stop_reason="error")

    monkeypatch.setattr(movie_service, "load_batch_movies", failing_load_batch_movies)

    deck_service._growth_cooldown_until = None
    try:
        swiped: set = set()
        deck_service._maybe_grow_catalog(db, u1, room, swiped)
        _wait_growth_idle()
        assert calls["n"] == 1
        assert deck_service._growth_cooldown_until is not None
        expected = datetime.now(timezone.utc) + timedelta(minutes=settings.CATALOG_GROWTH_COOLDOWN_MINUTES)
        assert abs((deck_service._growth_cooldown_until - expected).total_seconds()) < 5

        # В пределах паузы повторное пересечение порога не запускает догрузку.
        deck_service._maybe_grow_catalog(db, u1, room, swiped)
        assert calls["n"] == 1

        # После истечения паузы — догрузка снова запускается.
        deck_service._growth_cooldown_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        deck_service._maybe_grow_catalog(db, u1, room, swiped)
        _wait_growth_idle()
        assert calls["n"] == 2
    finally:
        deck_service._growth_cooldown_until = None


def test_growth_pause_sources_exhausted_is_long_and_blocks_retry(db, make_user, make_room, monkeypatch):
    monkeypatch.delattr(deck_service, "_start_background_growth")
    u1 = make_user(1503)
    room = make_room(u1, [1503])

    calls = {"n": 0}

    def empty_pass_end(session, count=10):
        calls["n"] += 1
        return LoadBatchResult(loaded=0, stop_reason="pass_end", new_in_pass=0)

    monkeypatch.setattr(movie_service, "load_batch_movies", empty_pass_end)

    deck_service._growth_cooldown_until = None
    try:
        deck_service._maybe_grow_catalog(db, u1, room, set())
        _wait_growth_idle()
        assert calls["n"] == 1
        assert deck_service._growth_cooldown_until is not None
        expected = datetime.now(timezone.utc) + timedelta(hours=settings.CATALOG_SOURCES_EXHAUSTED_COOLDOWN_HOURS)
        assert abs((deck_service._growth_cooldown_until - expected).total_seconds()) < 5

        # Длинная пауза активна — новая попытка не стартует.
        deck_service._maybe_grow_catalog(db, u1, room, set())
        assert calls["n"] == 1
    finally:
        deck_service._growth_cooldown_until = None


def test_growth_pause_pass_end_with_new_movies_sets_no_cooldown(db, make_user, make_room, monkeypatch):
    monkeypatch.delattr(deck_service, "_start_background_growth")
    u1 = make_user(1504)
    room = make_room(u1, [1504])

    monkeypatch.setattr(
        movie_service,
        "load_batch_movies",
        lambda session, count=10: LoadBatchResult(loaded=1, stop_reason="pass_end", new_in_pass=1),
    )

    deck_service._growth_cooldown_until = None
    deck_service._maybe_grow_catalog(db, u1, room, set())
    _wait_growth_idle()
    assert deck_service._growth_cooldown_until is None
