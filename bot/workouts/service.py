from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog
from bot.workouts.domain import InvalidWorkout, LoggedWorkout, WorkoutRecord
from bot.workouts.repository import WorkoutRepository


class ExerciseNotAvailable(InvalidWorkout):
    pass


async def _catalog_names(
    session: AsyncSession, record: WorkoutRecord
) -> dict[int, str]:
    """
    Названия упражнений тренировки, если все они доступны пользователю.

    Проверка здесь, а не в обработчике выбора упражнения: между выбором и
    сохранением упражнение могли удалить, а другой способ ввода мог выбора
    не делать вовсе. Название берём из каталога, а не из черновика: это
    источник правды.
    """
    exercise_ids = {
        entry.exercise_id for entry in record.exercises if entry.exercise_id is not None
    }
    available = await Catalog(session).get_visible_many(exercise_ids, record.user_id)
    if missing := exercise_ids - available.keys():
        raise ExerciseNotAvailable(f"exercises not available: {sorted(missing)}")
    return {ex_id: info.name for ex_id, info in available.items()}


async def record_workout(session: AsyncSession, record: WorkoutRecord) -> int:
    """Сохраняет тренировку, если все её упражнения доступны пользователю."""
    names = await _catalog_names(session, record)
    workout_id = await WorkoutRepository(session).add(record, names)
    await session.commit()
    return workout_id


def check_deleted_entries(record: WorkoutRecord, before: LoggedWorkout) -> None:
    """
    Удалённое из каталога упражнение можно оставить в тренировке, но не
    добавить: иначе через правку можно было бы записать любое название.
    """
    kept = {ex.name for ex in before.exercises if ex.exercise_id is None}
    for entry in record.exercises:
        if entry.exercise_id is None and entry.name not in kept:
            raise InvalidWorkout(f"deleted exercise can't be added: {entry.name}")


async def update_workout(
    session: AsyncSession, workout_id: int, record: WorkoutRecord
) -> bool:
    """Заменяет тренировку целиком. False — её нет или она чужая."""
    repo = WorkoutRepository(session)
    before = await repo.get(workout_id, record.user_id)
    if before is None:
        return False
    check_deleted_entries(record, before)
    names = await _catalog_names(session, record)
    # тренировку могли удалить между чтением и заменой
    if not await repo.replace(workout_id, record, names):
        return False
    await session.commit()
    return True


async def delete_workout(session: AsyncSession, workout_id: int, user_id: int) -> bool:
    """False — тренировки нет или она чужая."""
    deleted = await WorkoutRepository(session).delete(workout_id, user_id)
    if deleted:
        await session.commit()
    return deleted
