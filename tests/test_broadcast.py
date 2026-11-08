import asyncio

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.methods import SendMessage

from bot.users.broadcast import send_all

METHOD = SendMessage(chat_id=1, text="hi")


class FakeBot:
    def __init__(self, errors=None):
        # ошибка для chat_id — один раз, следующая попытка проходит
        self.errors = errors or {}
        self.sent = []

    async def send_message(self, chat_id, text):
        if error := self.errors.pop(chat_id, None):
            raise error
        self.sent.append((chat_id, text))


def test_sends_to_everyone():
    bot = FakeBot()
    assert asyncio.run(send_all(bot, [1, 2], "hi")) == (2, 0)
    assert bot.sent == [(1, "hi"), (2, "hi")]


def test_skips_blocked_and_missing_chats():
    bot = FakeBot(
        {
            1: TelegramForbiddenError(METHOD, "Forbidden: bot was blocked by the user"),
            2: TelegramBadRequest(METHOD, "Bad Request: chat not found"),
        }
    )
    assert asyncio.run(send_all(bot, [1, 2, 3], "hi")) == (1, 2)
    assert bot.sent == [(3, "hi")]


def test_waits_and_retries_on_flood_limit():
    bot = FakeBot({1: TelegramRetryAfter(METHOD, "Too Many Requests", retry_after=0)})
    assert asyncio.run(send_all(bot, [1], "hi")) == (1, 0)
    assert bot.sent == [(1, "hi")]
