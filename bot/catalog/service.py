from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.models import Exercise
from bot.catalog.repository import ExerciseRepository


async def add_exercise(
    session: AsyncSession, name: str, user_id: int, muscle_names: list[str]
) -> Exercise | None:
    """None, если упражнение с таким названием уже доступно пользователю."""
    exercise = await ExerciseRepository(session).add(name, user_id, muscle_names)
    if exercise is not None:
        await session.commit()
    return exercise


async def delete_exercise(
    session: AsyncSession, exercise_id: int, user_id: int
) -> bool:
    """False, если упражнения нет или оно не личное."""
    deleted = await ExerciseRepository(session).delete(exercise_id, user_id)
    if deleted:
        await session.commit()
    return deleted
