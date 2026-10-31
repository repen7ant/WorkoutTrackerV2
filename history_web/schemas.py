"""Доменные объекты тренировок ↔ JSON для страницы."""

from decimal import Decimal
from typing import Any

from bot.workouts.domain import LoggedWorkout, SetEntry
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
