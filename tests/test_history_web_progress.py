from datetime import date
from decimal import Decimal

from bot.workouts.domain import LoggedExercise, LoggedWorkout, SetEntry
from history_web.progress import Progress, build_progress


def s(weight=None, reps=None, seconds=None):
    return SetEntry(Decimal(weight) if weight else None, reps, seconds)


def w(day, *sets):
    return LoggedWorkout(
        id=day,
        date=date(2026, 10, day),
        notes=None,
        exercises=[LoggedExercise(7, "Bench Press", list(sets))],
    )


def test_weighted_takes_max_weight_per_workout():
    p = build_progress([w(1, s("60", 5), s("70", 3)), w(3, s("72.5", 3))])
    assert p.metric == "weight"
    assert [pt.value for pt in p.points] == [Decimal("70"), Decimal("72.5")]
    assert p.points[0].sets == [s("60", 5), s("70", 3)]


def test_bw_only_workout_skipped_for_weighted_exercise():
    p = build_progress([w(1, s(reps=10)), w(3, s("10", 8))])
    assert [pt.date for pt in p.points] == [date(2026, 10, 3)]


def test_bodyweight_takes_max_reps():
    p = build_progress([w(1, s(reps=8), s(reps=10))])
    assert (p.metric, p.points[0].value) == ("reps", 10)


def test_timed_takes_max_seconds():
    p = build_progress([w(1, s(seconds=45), s(seconds=60))])
    assert (p.metric, p.points[0].value) == ("seconds", 60)


def test_no_workouts():
    assert build_progress([]) == Progress(metric="weight", points=[])
