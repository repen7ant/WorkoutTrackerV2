"""
Рассылка всем пользователям бота — например, анонс обновления.

На сервере, в ~/workout-tracker:
docker compose -f docker-compose.prod.yaml exec bot uv run -m bot.broadcast "текст"
"""

import asyncio
import sys

from aiogram import Bot

from bot.config import Settings
from bot.db.session import AsyncSessionLocal
from bot.users.broadcast import send_all
from bot.users.service import all_user_ids

MAX_MESSAGE = 4096  # лимит Telegram: длиннее не уйдёт никому


async def broadcast(text: str) -> None:
    async with AsyncSessionLocal() as session:
        user_ids = await all_user_ids(session)
    print(f"Message for {len(user_ids)} users:\n\n{text}\n")
    # input() остановил бы цикл событий — ждём ответ в отдельном потоке
    answer = await asyncio.to_thread(input, "Send? [y/N] ")
    if answer.strip().lower() != "y":
        print("Cancelled")
        return
    bot = Bot(token=Settings().bot.token.get_secret_value())
    try:
        sent, skipped = await send_all(bot, user_ids, text)
    finally:
        await bot.session.close()
    print(f"Sent: {sent}, skipped (blocked the bot or deleted the account): {skipped}")


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        sys.exit('usage: uv run -m bot.broadcast "text"')
    text = sys.argv[1].strip()
    if len(text) > MAX_MESSAGE:
        sys.exit(f"text is longer than {MAX_MESSAGE} characters")
    asyncio.run(broadcast(text))


main()
