from datetime import date
from decimal import Decimal

from bot.workouts.domain import LoggedExercise, LoggedWorkout, SetEntry
from history_web.schemas import workout_to_json


def test_workout_to_json():
    w = LoggedWorkout(
        id=42,
        date=date(2026, 10, 30),
        notes="week 3",
        exercises=[
            LoggedExercise(7, "Bench Press", [SetEntry(Decimal("62.50"), 5)]),
            LoggedExercise(None, "Old custom", [SetEntry(None, seconds=60)]),
        ],
    )
    assert workout_to_json(w) == {
        "id": 42,
        "date": "2026-10-30",
        "notes": "week 3",
        "exercises": [
            {
                "exercise_id": 7,
                "name": "Bench Press",
                "sets": [{"weight": 62.5, "reps": 5, "seconds": None}],
            },
            {
                "exercise_id": None,
                "name": "Old custom",
                "sets": [{"weight": None, "reps": None, "seconds": 60}],
            },
        ],
    }
