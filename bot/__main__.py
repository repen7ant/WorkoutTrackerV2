import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from structlog.typing import FilteringBoundLogger

from bot.config import Settings
from bot.db.session import AsyncSessionLocal
from bot.handlers import get_routers
from bot.logging_config import get_structlog_config
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.fsm import EXERCISES_DESTINY, SubFSMMiddleware
from bot.middlewares.user import UserMiddleware

logger: FilteringBoundLogger = structlog.get_logger()


async def main() -> None:
    settings = Settings()
    structlog.configure(**get_structlog_config(settings.logs))

    bot = Bot(token=settings.bot.token.get_secret_value())

    # with_destiny=True обязателен: без него DefaultKeyBuilder отказывается
    # строить ключ для дорожки, отличной от дефолтной, и вторая FSM-дорожка
    # (диалоги упражнений) падает с ValueError.
    storage = RedisStorage.from_url(
        settings.redis.url,
        key_builder=DefaultKeyBuilder(with_destiny=True),
    )

    dp = Dispatcher(storage=storage)
    dp.update.middleware(DbSessionMiddleware(AsyncSessionLocal))
    dp.update.middleware(UserMiddleware())
    dp.update.middleware(SubFSMMiddleware(EXERCISES_DESTINY))

    dp.include_routers(*get_routers())

    await logger.ainfo("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await storage.close()
        await logger.ainfo("Bot stopped")


asyncio.run(main())
