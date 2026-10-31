import asyncio
from datetime import date
from decimal import Decimal

from bot.workouts import service
from bot.workouts.domain import (
    ExerciseEntry,
    LoggedExercise,
    LoggedWorkout,
    SetEntry,
    WorkoutRecord,
)

BENCH = [SetEntry(Decimal("60.00"), 5)]


class FakeSession:
    committed = False

    async def commit(self):
        self.committed = True


class VanishingRepo:
    """Тренировку удалили между чтением и заменой — например, с другого
    устройства."""

    def __init__(self, session):
        pass

    async def get(self, workout_id, user_id):
        return LoggedWorkout(
            id=workout_id,
            date=date(2026, 10, 30),
            notes=None,
            exercises=[LoggedExercise(7, "Bench Press", BENCH)],
        )

    async def replace(self, workout_id, record, names):
        return False


async def bench_names(session, record):
    return {7: "Bench Press"}


def test_update_reports_workout_deleted_meanwhile(monkeypatch):
    monkeypatch.setattr(service, "WorkoutRepository", VanishingRepo)
    monkeypatch.setattr(service, "_catalog_names", bench_names)
    session = FakeSession()
    record = WorkoutRecord.create(
        1, date(2026, 10, 30), None, [ExerciseEntry.create(7, BENCH)]
    )

    assert asyncio.run(service.update_workout(session, 1, record)) is False
    assert not session.committed
