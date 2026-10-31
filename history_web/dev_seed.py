"""
Тестовые тренировки для проверки Mini App: 12 недель, пн/ср/пт.

Только для локальной базы: uv run -m history_web.dev_seed <user_id>
"""

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog
from bot.catalog.service import add_exercise
from bot.config import Settings
from bot.db.session import AsyncSessionLocal
from bot.users.service import get_or_register
from bot.workouts.domain import ExerciseEntry, SetEntry, WorkoutRecord
from bot.workouts.repository import WorkoutRepository
from bot.workouts.service import record_workout

WEEKS = 12
TRAINING_DAYS = (0, 2, 4)
LOCAL_HOSTS = {"localhost", "127.0.0.1"}


async def exercise_id(session: AsyncSession, name: str, user_id: int) -> int:
    found, _ = await Catalog(session).search(name, user_id)
    match = next((ex.id for ex in found if ex.name == name), None)
    if match is not None:
        return match
    # планки в общем каталоге нет — заводим личную
    return (await add_exercise(session, name, user_id, ["Core"])).id


def build_workout(user_id: int, day: date, i: int, ids: dict[str, int]):
    bench = Decimal("60") + Decimal("1.25") * i
    squat = Decimal("80") + Decimal("2.5") * (i // 2)
    pull_ups = 6 + i // 6
    plank = 30 + 5 * (i // 3)
    exercises = [
        ExerciseEntry.create(
            ids["Bench Press"], [SetEntry.create(bench, 5) for _ in range(3)]
        ),
        ExerciseEntry.create(
            ids["Squat"], [SetEntry.create(squat, 5) for _ in range(3)]
        ),
        ExerciseEntry.create(
            ids["Pull-Up"],
            [SetEntry.create(None, r) for r in (pull_ups, pull_ups, pull_ups - 1)],
        ),
        ExerciseEntry.create(
            ids["Plank"], [SetEntry.create(None, seconds=plank) for _ in range(2)]
        ),
    ]
    notes = f"week {i // 3 + 1}" if day.weekday() == 0 else None
    return WorkoutRecord.create(user_id, day, notes, exercises)


async def seed(user_id: int) -> None:
    async with AsyncSessionLocal() as session:
        await get_or_register(session, user_id, None)
        workouts, _ = await WorkoutRepository(session).page(user_id, 1)
        if workouts:
            print(f"User {user_id} already has workouts, skipping")
            return

        names = ("Bench Press", "Squat", "Pull-Up", "Plank")
        ids = {name: await exercise_id(session, name, user_id) for name in names}

        today = date.today()
        days = [
            today - timedelta(days=d)
            for d in range(WEEKS * 7, -1, -1)
            if (today - timedelta(days=d)).weekday() in TRAINING_DAYS
        ]
        for i, day in enumerate(days):
            await record_workout(session, build_workout(user_id, day, i, ids))
        print(f"Seeded {len(days)} workouts for user {user_id}")


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("usage: uv run -m history_web.dev_seed <user_id>")
    host = urlparse(Settings().db.url).hostname
    if host not in LOCAL_HOSTS:
        sys.exit(f"refusing to seed non-local database ({host})")
    asyncio.run(seed(int(sys.argv[1])))


main()
