from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.users.models import User
from bot.users.settings import LOG_SIZES, UTC_OFFSETS, Setting


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


async def update_setting(
    session: AsyncSession, user: User, setting: Setting, value: int
) -> None:
    match setting:
        case Setting.DATE:
            user.ask_workout_date = bool(value)
        case Setting.NOTES:
            user.ask_workout_notes = bool(value)
        case Setting.LOG:
            if value not in LOG_SIZES:
                return
            user.exercise_log_size = value
        case Setting.TIMEZONE:
            if value not in UTC_OFFSETS:
                return
            user.utc_offset = value
    await session.commit()


async def all_user_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(select(User.id).order_by(User.id))
    return list(result.scalars().all())
