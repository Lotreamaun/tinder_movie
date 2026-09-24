"""Тесты обработчика `/room_info` бота (change fix-room-info-large-room).

Регрессия: имя/юзернейм участника с непарным спецсимволом Markdown (`_`, `*`,
` ` ` `, `[`) вместе с `parse_mode='Markdown'` приводило к ошибке отправки
сообщения Telegram Bot API («Can't parse entities»), тонувшей в общем
`except Exception`. Обработчик теперь отправляет сообщение обычным текстом.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.bot.handlers import room_info
from app.services.user_service import user_service


def _make_update(telegram_id: int):
    message = MagicMock()
    message.reply_text = AsyncMock()
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=telegram_id),
        message=message,
    )


def test_room_info_with_markdown_special_chars_in_name(db, make_user, make_room):
    creator = make_user(910001, first_name="Host")
    # first_name/username с непарными спецсимволами Markdown, ломавшими
    # parse_mode='Markdown' до фикса.
    user_service.create_user(
        db,
        telegram_id=910002,
        first_name="Ann_*[Weird`",
        username="weird_*name",
    )
    make_room(creator, [910001, 910002])

    update = _make_update(910001)
    asyncio.run(room_info(update, MagicMock()))

    update.message.reply_text.assert_awaited_once()
    args, kwargs = update.message.reply_text.call_args
    assert kwargs.get("parse_mode") is None
    text = args[0]
    assert "Ann_*[Weird`" in text
    assert "weird_*name" in text
    assert "Произошла ошибка" not in text


def test_room_info_with_three_or_more_participants(db, make_user, make_room):
    creator = make_user(910101, first_name="Host")
    make_user(910102, first_name="Second")
    make_user(910103, first_name="Third")
    make_room(creator, [910101, 910102, 910103])

    update = _make_update(910101)
    asyncio.run(room_info(update, MagicMock()))

    update.message.reply_text.assert_awaited_once()
    args, kwargs = update.message.reply_text.call_args
    assert kwargs.get("parse_mode") is None
    text = args[0]
    assert "Host" in text
    assert "Second" in text
    assert "Third" in text
    assert "(3)" in text
    assert "Произошла ошибка" not in text
