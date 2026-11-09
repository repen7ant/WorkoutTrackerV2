"""Доменные объекты тренировок ↔ JSON для страницы."""

import re
from datetime import date, time
from decimal import Decimal
from typing import Any

from bot.workouts.domain import (
    ExerciseEntry,
    InvalidWorkout,
    LoggedWorkout,
    SetEntry,
    WorkoutRecord,
    duration_minutes,
)
from history_web.progress import Progress

_HH_MM = re.compile(r"\d{2}:\d{2}")


def _number(value: Decimal | int | None) -> float | int | None:
    return float(value) if isinstance(value, Decimal) else value


def _time_to_json(value: time | None) -> str | None:
    return None if value is None else f"{value:%H:%M}"


def set_to_json(s: SetEntry) -> dict[str, Any]:
    return {"weight": _number(s.weight), "reps": s.reps, "seconds": s.seconds}


def workout_summary_to_json(w: LoggedWorkout) -> dict[str, Any]:
    duration = None
    if w.start_time is not None and w.end_time is not None:
        duration = duration_minutes(w.start_time, w.end_time)
    return {
        "id": w.id,
        "date": w.date.isoformat(),
        "notes": w.notes,
        "start_time": _time_to_json(w.start_time),
        "end_time": _time_to_json(w.end_time),
        "duration_minutes": duration,
    }


def workout_to_json(w: LoggedWorkout) -> dict[str, Any]:
    return {
        **workout_summary_to_json(w),
        "exercises": [
            {
                "exercise_id": ex.exercise_id,
                "name": ex.name,
                "notes": ex.notes,
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
    # PUT заменяет тренировку целиком: старая страница из кэша, которая не знает
    # о заметках, без этой проверки молча стёрла бы их
    if "notes" not in data:
        raise InvalidWorkout("exercise notes are missing, reopen the app")
    notes = data["notes"]
    if notes is not None and not isinstance(notes, str):
        raise InvalidWorkout("exercise notes must be a string")
    sets = [_set_from_json(s) for s in data["sets"]]
    exercise_id = _optional_int(data.get("exercise_id"), "exercise_id")
    if exercise_id is not None:
        return ExerciseEntry.create(exercise_id, sets, notes)
    if not isinstance(data.get("name"), str):
        raise InvalidWorkout("deleted exercise must have a name")
    return ExerciseEntry.deleted(data["name"], sets, notes)


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
    exercises = [_exercise_from_json(ex) for ex in body["exercises"]]
    # как с заметками упражнений: старая страница из кэша, которая не знает
    # о времени, без этой проверки молча стёрла бы его
    if "start_time" not in body or "end_time" not in body:
        raise InvalidWorkout("workout time is missing, reopen the app")
    return WorkoutRecord.create(
        user_id,
        workout_date,
        notes,
        exercises,
        start_time=_time_from_json(body["start_time"], "start_time"),
        end_time=_time_from_json(body["end_time"], "end_time"),
    )


def _time_from_json(value: Any, field: str) -> time | None:
    if value is None:
        return None
    if not (isinstance(value, str) and _HH_MM.fullmatch(value)):
        raise InvalidWorkout(f"{field} must be HH:MM")
    try:
        return time.fromisoformat(value)
    except ValueError as e:  # 25:00
        raise InvalidWorkout(f"{field} must be HH:MM") from e
