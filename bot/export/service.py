from datetime import date, time
from typing import NotRequired, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog
from bot.workouts.domain import SetEntry
from bot.workouts.repository import WorkoutRepository


class ExportExercise(TypedDict):
    name: str
    muscles: list[str]
    sets: list[SetEntry]
    notes: str | None


class ExportWorkout(TypedDict):
    date: date
    start_time: time | None
    end_time: time | None
    notes: str | None
    exercises: list[ExportExercise]
    program_day: NotRequired[str | None]
    program_week: NotRequired[int | None]


async def collect_workouts(
    session: AsyncSession, user_id: int, since: date | None
) -> list[ExportWorkout]:
    """
    Тренировки с названиями и мышцами упражнений, от старых к новым; внутри
    тренировки упражнения идут в порядке выполнения, подходы — в порядке ввода.
    """
    workouts = await WorkoutRepository(session).since(user_id, since)
    if not workouts:
        return []

    exercise_ids = {
        ex.exercise_id
        for w in workouts
        for ex in w.exercises
        if ex.exercise_id is not None
    }
    muscles = await Catalog(session).muscles(exercise_ids)

    return [
        ExportWorkout(
            date=w.date,
            start_time=w.start_time,
            end_time=w.end_time,
            notes=w.notes,
            program_day=w.program_day,
            program_week=w.program_week,
            exercises=[
                ExportExercise(
                    name=ex.name,
                    # у удалённого упражнения мышц уже нет
                    muscles=muscles.get(ex.exercise_id, []),
                    sets=ex.sets,
                    notes=ex.notes,
                )
                for ex in w.exercises
            ],
        )
        for w in workouts
    ]


async def has_workouts(session: AsyncSession, user_id: int, since: date | None) -> bool:
    """Есть ли тренировки с даты since — без загрузки лога."""
    return await WorkoutRepository(session).exists_since(user_id, since)


async def catalog_exercises(
    session: AsyncSession, user_id: int
) -> dict[str, list[str]]:
    """Весь доступный пользователю каталог: название -> мышцы. ИИ выбирает
    упражнения для программы отсюда, а не придумывает названия."""
    catalog = Catalog(session)
    exercises = await catalog.visible(user_id)
    muscles = await catalog.muscles({ex.id for ex in exercises})
    return {ex.name: muscles.get(ex.id, []) for ex in exercises}
