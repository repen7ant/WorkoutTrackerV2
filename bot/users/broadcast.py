import asyncio

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

# Telegram пропускает около 30 сообщений в секунду
PAUSE = 0.05


async def send_all(bot: Bot, user_ids: list[int], text: str) -> tuple[int, int]:
    """
    Отправляет text каждому пользователю. Возвращает (доставлено, пропущено):
    пропускает тех, кто заблокировал бота или удалил аккаунт.
    """
    sent = skipped = 0
    for user_id in user_ids:
        try:
            await _send(bot, user_id, text)
        except (TelegramForbiddenError, TelegramBadRequest):
            skipped += 1
        else:
            sent += 1
        await asyncio.sleep(PAUSE)
    return sent, skipped


async def _send(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        await bot.send_message(user_id, text)
