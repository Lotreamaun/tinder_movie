"""Тесты RoomService.join_room, связанные с уведомлением о присоединении
(change notify-room-join): ошибка уведомления не должна ломать присоединение.
"""
from unittest.mock import patch

from app.services.room_service import room_service


def test_join_room_succeeds_even_if_notification_raises(db, make_user, make_room):
    creator = make_user(930001, first_name="Host")
    joiner = make_user(930002, first_name="Newbie")
    room = make_room(creator, [930001])

    with patch(
        "app.services.notification_service.notification_service.send_room_join_notification",
        side_effect=RuntimeError("boom"),
    ):
        result = room_service.join_room(db, joiner, room.id)

    assert result.participants == [930001, 930002]

    refreshed = room_service.get_room_by_code(db, room.id)
    assert refreshed.participants == [930001, 930002]


def test_join_room_calls_send_room_join_notification(db, make_user, make_room):
    creator = make_user(930011, first_name="Host")
    joiner = make_user(930012, first_name="Newbie")
    room = make_room(creator, [930011])

    with patch(
        "app.services.notification_service.notification_service.send_room_join_notification"
    ) as mock_notify:
        room_service.join_room(db, joiner, room.id)

    mock_notify.assert_called_once()
    args, _ = mock_notify.call_args
    called_room, called_user = args[0], args[1]
    assert called_room.id == room.id
    assert called_user.telegram_id == 930012
