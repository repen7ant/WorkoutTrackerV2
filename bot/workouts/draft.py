"""
Черновик тренировки в FSM и его превращение в WorkoutRecord.

  exercises: [{"exercise_id": int, "exercise_name": str, "notes": str | None,
               "sets": [{"weight": Decimal | None, "reps": int | None,
                         "seconds": int | None}]}]

Ключи seconds и notes появились позже — с подходами на время и заметками
к упражнениям: в черновиках, начатых раньше, их нет, и такие черновики
должны сохраняться так же.
"""

from datetime import date
from typing import Any

from bot.workouts.domain import ExerciseEntry, SetEntry, WorkoutRecord


def set_to_fsm(entry: SetEntry) -> dict[str, Any]:
    return {"weight": entry.weight, "reps": entry.reps, "seconds": entry.seconds}


def sets_from_fsm(sets: list[dict[str, Any]]) -> list[SetEntry]:
    return [
        SetEntry(weight=s["weight"], reps=s["reps"], seconds=s.get("seconds"))
        for s in sets
    ]


def build_record(user_id: int, data: dict[str, Any]) -> WorkoutRecord:
    """Собирает тренировку через доменные конструкторы — с их проверками."""
    exercises = [
        ExerciseEntry.create(
            ex["exercise_id"],
            [
                SetEntry.create(s["weight"], s["reps"], s.get("seconds"))
                for s in ex["sets"]
            ],
            ex.get("notes"),
        )
        for ex in data.get("exercises", [])
    ]
    return WorkoutRecord.create(
        user_id=user_id,
        workout_date=date.fromisoformat(data["workout_date"]),
        notes=data.get("notes"),
        exercises=exercises,
    )
