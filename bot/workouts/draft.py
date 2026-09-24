"""
Черновик тренировки в FSM и его превращение в WorkoutRecord.

Формат данных в FSM не менялся: тренировки, начатые до обновления бота,
сохраняются так же.

  exercises: [{"exercise_id": int, "exercise_name": str,
               "sets": [{"weight": Decimal | None, "reps": int}]}]
"""

from datetime import date
from typing import Any

from bot.workouts.domain import ExerciseEntry, SetEntry, WorkoutRecord


def set_to_fsm(entry: SetEntry) -> dict[str, Any]:
    return {"weight": entry.weight, "reps": entry.reps}


def sets_from_fsm(sets: list[dict[str, Any]]) -> list[SetEntry]:
    return [SetEntry(weight=s["weight"], reps=s["reps"]) for s in sets]


def build_record(user_id: int, data: dict[str, Any]) -> WorkoutRecord:
    """Собирает тренировку через доменные конструкторы — с их проверками."""
    exercises = [
        ExerciseEntry.create(
            ex["exercise_id"],
            [SetEntry.create(s["weight"], s["reps"]) for s in ex["sets"]],
        )
        for ex in data.get("exercises", [])
    ]
    return WorkoutRecord.create(
        user_id=user_id,
        workout_date=date.fromisoformat(data["workout_date"]),
        notes=data.get("notes"),
        exercises=exercises,
    )
