from datetime import date
from decimal import Decimal
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog
from bot.workouts.repository import WorkoutRepository


class ExportSet(TypedDict):
    weight: Decimal | None
    reps: int


class ExportExercise(TypedDict):
    name: str
    muscles: list[str]
    sets: list[ExportSet]


class ExportWorkout(TypedDict):
    date: date
    notes: str | None
    exercises: list[ExportExercise]


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
            notes=w.notes,
            exercises=[
                ExportExercise(
                    name=ex.name,
                    # у удалённого упражнения мышц уже нет
                    muscles=muscles.get(ex.exercise_id, []),
                    sets=[ExportSet(weight=s.weight, reps=s.reps) for s in ex.sets],
                )
                for ex in w.exercises
            ],
        )
        for w in workouts
    ]
