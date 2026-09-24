from datetime import date
from decimal import Decimal

import pytest

from bot.workouts.domain import (
    MAX_REPS,
    ExerciseEntry,
    InvalidWorkout,
    SetEntry,
    WorkoutRecord,
)
from bot.workouts.draft import build_record
from bot.workouts.handlers.recording import parse_set


@pytest.mark.parametrize(
    ("weight", "reps"),
    [
        (None, 0),
        (None, MAX_REPS + 1),
        (Decimal("-1"), 5),
        (Decimal("NaN"), 5),
        (Decimal("Infinity"), 5),
        (Decimal("999.995"), 5),  # после округления — 1000.00
    ],
)
def test_set_out_of_bounds(weight, reps):
    with pytest.raises(InvalidWorkout):
        SetEntry.create(weight, reps)


def test_set_weight_rounded_to_column_scale():
    assert SetEntry.create(Decimal("60.555"), 8).weight == Decimal("60.56")


def test_exercise_needs_sets():
    with pytest.raises(InvalidWorkout):
        ExerciseEntry.create(1, [])


def test_workout_needs_exercises():
    with pytest.raises(InvalidWorkout):
        WorkoutRecord.create(1, date(2026, 1, 1), None, [])


def test_positions_follow_exercise_order():
    sets = [SetEntry.create(None, 1)]
    record = WorkoutRecord.create(
        1,
        date(2026, 1, 1),
        "  ",
        [ExerciseEntry.create(7, sets), ExerciseEntry.create(3, sets)],
    )
    assert [(pos, e.exercise_id) for pos, e in record.positioned()] == [(1, 7), (2, 3)]
    assert record.notes is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("100x5", SetEntry(Decimal("100.00"), 5)),
        (" bwX10 ", SetEntry(None, 10)),
        ("100", None),
        ("axb", None),
        ("1000x5", None),
        ("nanx5", None),
        ("100x0", None),
        (None, None),
    ],
)
def test_parse_set(text, expected):
    assert parse_set(text) == expected


def test_build_record_revalidates_fsm_data():
    """Черновик из FSM проходит те же правила, что и ввод в чате."""
    data = {
        "workout_date": "2026-01-01",
        "exercises": [
            {
                "exercise_id": 1,
                "exercise_name": "X",
                "sets": [{"weight": None, "reps": 0}],
            }
        ],
    }
    with pytest.raises(InvalidWorkout):
        build_record(1, data)
