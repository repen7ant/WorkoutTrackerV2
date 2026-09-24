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
    available = await Catalog(session).get_visible_many(exercise_ids, record.user_id)
    if missing := exercise_ids - available.keys():
        raise ExerciseNotAvailable(f"exercises not available: {sorted(missing)}")

    # название берём из каталога, а не из черновика: это источник правды
    names = {ex_id: info.name for ex_id, info in available.items()}
    workout_id = await WorkoutRepository(session).add(record, names)
    await session.commit()
    return workout_id
