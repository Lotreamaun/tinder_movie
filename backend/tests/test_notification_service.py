"""Тесты уведомления участников комнаты о присоединении нового человека
(change notify-room-join).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.error import TelegramError

from app.services.notification_service import notification_service
from app.services.user_service import user_service


class _SyncThread:
    """Подменяет threading.Thread — выполняет target синхронно, без реального потока."""

    def __init__(self, target=None, daemon=None):
        self._target = target

    def start(self):
        self._target()


@pytest.fixture()
def sync_bot(monkeypatch):
    """Даёт notification_service поддельного бота и делает фоновую отправку синхронной."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    monkeypatch.setattr(notification_service, "bot", bot)
    monkeypatch.setattr("app.services.notification_service.threading.Thread", _SyncThread)
    return bot


def test_send_room_join_notification_notifies_other_participants(db, make_user, make_room, sync_bot):
    creator = make_user(920001, first_name="Host")
    joiner = make_user(920002, first_name="Newbie")
    room = make_room(creator, [920001, 920002])

    notification_service.send_room_join_notification(room, joiner, db)

    sync_bot.send_message.assert_awaited_once()
    _, kwargs = sync_bot.send_message.call_args
    assert kwargs["chat_id"] == 920001
    assert "Newbie" in kwargs["text"]
    assert kwargs.get("parse_mode") is None


def test_send_room_join_notification_does_not_notify_joiner(db, make_user, make_room, sync_bot):
    creator = make_user(920011, first_name="Host")
    joiner = make_user(920012, first_name="Newbie")
    room = make_room(creator, [920011, 920012])

    notification_service.send_room_join_notification(room, joiner, db)

    chat_ids = {call.kwargs["chat_id"] for call in sync_bot.send_message.call_args_list}
    assert 920012 not in chat_ids


def test_send_room_join_notification_markdown_special_chars_in_name(db, make_user, make_room, sync_bot):
    creator = make_user(920021, first_name="Host")
    joiner = user_service.create_user(
        db, telegram_id=920022, first_name="Ann_*[Weird`", username="weird_*name"
    )
    room = make_room(creator, [920021, 920022])

    notification_service.send_room_join_notification(room, joiner, db)

    sync_bot.send_message.assert_awaited_once()
    _, kwargs = sync_bot.send_message.call_args
    assert "Ann_*[Weird`" in kwargs["text"]
    assert "weird_*name" in kwargs["text"]
    assert kwargs.get("parse_mode") is None


def test_send_room_join_notification_error_for_one_recipient_does_not_block_others(
    db, make_user, make_room, sync_bot
):
    creator = make_user(920031, first_name="Host")
    second = make_user(920032, first_name="Second")
    joiner = make_user(920033, first_name="Newbie")
    room = make_room(creator, [920031, 920032, 920033])

    sync_bot.send_message.side_effect = [TelegramError("blocked"), None]

    notification_service.send_room_join_notification(room, joiner, db)

    assert sync_bot.send_message.await_count == 2
    chat_ids = {call.kwargs["chat_id"] for call in sync_bot.send_message.call_args_list}
    assert chat_ids == {920031, 920032}


def test_send_room_join_notification_no_other_participants_skips_send(db, make_user, make_room, monkeypatch):
    bot = MagicMock()
    bot.send_message = AsyncMock()
    monkeypatch.setattr(notification_service, "bot", bot)

    def _forbidden_thread(*args, **kwargs):
        raise AssertionError("Фоновый поток не должен создаваться, если получателей нет")

    monkeypatch.setattr("app.services.notification_service.threading.Thread", _forbidden_thread)

    creator = make_user(920041, first_name="Host")
    room = make_room(creator, [920041])

    notification_service.send_room_join_notification(room, creator, db)

    bot.send_message.assert_not_awaited()


def test_send_room_join_notification_without_bot_token_does_nothing(db, make_user, make_room, monkeypatch):
    monkeypatch.setattr(notification_service, "bot", None)

    def _forbidden_thread(*args, **kwargs):
        raise AssertionError("Фоновый поток не должен создаваться без токена бота")

    monkeypatch.setattr("app.services.notification_service.threading.Thread", _forbidden_thread)

    creator = make_user(920051, first_name="Host")
    joiner = make_user(920052, first_name="Newbie")
    room = make_room(creator, [920051, 920052])

    notification_service.send_room_join_notification(room, joiner, db)
