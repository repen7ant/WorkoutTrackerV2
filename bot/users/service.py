from sqlalchemy.ext.asyncio import AsyncSession

from bot.users.models import User


async def get_or_register(
    session: AsyncSession, user_id: int, username: str | None
) -> User:
    """Регистрирует при первой встрече (по telegram id) и обновляет username:
    в Telegram он меняется, а в БД оставался тем, что был при первой встрече."""
    user = await session.get(User, user_id)
    if user is None:
        user = User(id=user_id, username=username)
        session.add(user)
        await session.commit()
    elif user.username != username:
        user.username = username
        await session.commit()
    return user
