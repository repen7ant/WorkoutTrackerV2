from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog
from bot.workouts.domain import InvalidWorkout, WorkoutRecord
from bot.workouts.repository import WorkoutRepository


class ExerciseNotAvailable(InvalidWorkout):
    pass


async def record_workout(session: AsyncSession, record: WorkoutRecord) -> int:
    """
    Сохраняет тренировку, если все её упражнения доступны пользователю.

    Проверка здесь, а не в обработчике выбора упражнения: между выбором и
    сохранением упражнение могли удалить, а другой способ ввода мог выбора
    не делать вовсе.
    """
    exercise_ids = {entry.exercise_id for entry in record.exercises}
    available = await Catalog(session).visible_ids(exercise_ids, record.user_id)
    if missing := exercise_ids - available:
        raise ExerciseNotAvailable(f"exercises not available: {sorted(missing)}")

    workout_id = await WorkoutRepository(session).add(record)
    await session.commit()
    return workout_id
