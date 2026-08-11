"""Тесты общего колода фильмов комнаты (change shared-deck)."""
from uuid import UUID

from app.models.room_deck import RoomDeck
from app.services import deck_service as deck_service_module
from app.services.deck_service import deck_service
from app.services.movie_service import movie_service
from app.services.swipe_service import swipe_service


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
