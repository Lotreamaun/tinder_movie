"""Тесты общего колода фильмов комнаты (change shared-deck)."""
from uuid import UUID

from app.database import SessionLocal
from app.models.room_deck import RoomDeck
from app.services import deck_service as deck_service_module
from app.services.deck_service import deck_service
from app.services.movie_service import movie_service
from app.services.swipe_service import swipe_service
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

    # Каталог исчерпан: запрос возвращает фильм (повтор), а не None
    movie = deck_service.get_next_movie_for_room(db, u1, room.id)
    assert movie is not None
