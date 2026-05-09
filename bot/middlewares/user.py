from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.users import User as UserModel


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        session: AsyncSession = data["session"]
        db_user = await session.get(UserModel, user.id)

        if db_user is None:
            db_user = UserModel(
                username=user.username,
                id=user.id,
            )
            session.add(db_user)
            await session.commit()

        data["db_user"] = db_user
        return await handler(event, data)
