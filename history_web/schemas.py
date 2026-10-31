"""Доменные объекты тренировок ↔ JSON для страницы."""

from datetime import date
from decimal import Decimal
from typing import Any

from bot.workouts.domain import (
    ExerciseEntry,
    InvalidWorkout,
    LoggedWorkout,
    SetEntry,
    WorkoutRecord,
)
from history_web.progress import Progress


def _number(value: Decimal | int | None) -> float | int | None:
    return float(value) if isinstance(value, Decimal) else value


def set_to_json(s: SetEntry) -> dict[str, Any]:
    return {"weight": _number(s.weight), "reps": s.reps, "seconds": s.seconds}


def workout_summary_to_json(w: LoggedWorkout) -> dict[str, Any]:
    return {"id": w.id, "date": w.date.isoformat(), "notes": w.notes}


def workout_to_json(w: LoggedWorkout) -> dict[str, Any]:
    return {
        **workout_summary_to_json(w),
        "exercises": [
            {
                "exercise_id": ex.exercise_id,
                "name": ex.name,
                "sets": [set_to_json(s) for s in ex.sets],
            }
            for ex in w.exercises
        ],
    }


def progress_to_json(p: Progress) -> dict[str, Any]:
    return {
        "metric": p.metric,
        "points": [
            {
                "date": pt.date.isoformat(),
                "value": _number(pt.value),
                "sets": [set_to_json(s) for s in pt.sets],
            }
            for pt in p.points
        ],
    }


# Тело PUT приходит со страницы, поэтому форму проверяем здесь, а значения —
# доменными конструкторами. bool в JSON — тоже int для Python, его отсекаем.


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _optional_int(value: Any, field: str) -> int | None:
    if value is not None and not _is_int(value):
        raise InvalidWorkout(f"{field} must be an integer")
    return value


def _weight(value: Any) -> Decimal | None:
    if value is None:
        return None
    if not (_is_int(value) or isinstance(value, Decimal)):
        raise InvalidWorkout("weight must be a number")
    return Decimal(value)


def _set_from_json(data: Any) -> SetEntry:
    if not isinstance(data, dict):
        raise InvalidWorkout("set must be an object")
    return SetEntry.create(
        _weight(data.get("weight")),
        _optional_int(data.get("reps"), "reps"),
        _optional_int(data.get("seconds"), "seconds"),
    )


def _exercise_from_json(data: Any) -> ExerciseEntry:
    if not isinstance(data, dict):
        raise InvalidWorkout("exercise must be an object")
    if not isinstance(data.get("sets"), list):
        raise InvalidWorkout("sets must be a list")
    sets = [_set_from_json(s) for s in data["sets"]]
    exercise_id = _optional_int(data.get("exercise_id"), "exercise_id")
    if exercise_id is not None:
        return ExerciseEntry.create(exercise_id, sets)
    if not isinstance(data.get("name"), str):
        raise InvalidWorkout("deleted exercise must have a name")
    return ExerciseEntry.deleted(data["name"], sets)


def record_from_json(user_id: int, body: Any) -> WorkoutRecord:
    if not isinstance(body, dict):
        raise InvalidWorkout("workout must be an object")
    try:
        workout_date = date.fromisoformat(body.get("date"))
    except (TypeError, ValueError) as e:
        raise InvalidWorkout("date must be YYYY-MM-DD") from e
    notes = body.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise InvalidWorkout("notes must be a string")
    if not isinstance(body.get("exercises"), list):
        raise InvalidWorkout("exercises must be a list")
    return WorkoutRecord.create(
        user_id,
        workout_date,
        notes,
        [_exercise_from_json(ex) for ex in body["exercises"]],
    )
