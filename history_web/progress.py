"""Точки графика прогресса: одна тренировка — одна точка."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from bot.workouts.domain import LoggedWorkout, SetEntry

# по порядку приоритета: если у упражнения бывает вес, прогресс — в весе
METRICS = ("weight", "reps", "seconds")


@dataclass(frozen=True)
class Point:
    date: date
    value: Decimal | int
    sets: list[SetEntry]


@dataclass(frozen=True)
class Progress:
    metric: str
    points: list[Point]


def build_progress(workouts: list[LoggedWorkout]) -> Progress:
    """workouts — от старых к новым, в каждой только нужное упражнение."""
    sessions = [(w.date, [s for ex in w.exercises for s in ex.sets]) for w in workouts]
    metric = next(
        (
            m
            for m in METRICS
            if any(getattr(s, m) is not None for _, sets in sessions for s in sets)
        ),
        METRICS[0],
    )

    points = []
    for day, sets in sessions:
        values = [getattr(s, metric) for s in sets if getattr(s, metric) is not None]
        if values:
            points.append(Point(date=day, value=max(values), sets=sets))
    return Progress(metric=metric, points=points)
