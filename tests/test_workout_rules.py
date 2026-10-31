from datetime import date
from decimal import Decimal

import pytest

from bot.utils import fsm_json
from bot.workouts.domain import (
    MAX_REPS,
    MAX_SECONDS,
    ExerciseEntry,
    InvalidWorkout,
    LoggedExercise,
    LoggedWorkout,
    SetEntry,
    WorkoutRecord,
)
from bot.workouts.draft import build_record, set_to_fsm, sets_from_fsm
from bot.workouts.handlers.recording import parse_set
from bot.workouts.service import check_deleted_entries


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


def test_timed_set_keeps_seconds_instead_of_reps():
    assert SetEntry.create(Decimal("20"), seconds=90) == SetEntry(
        Decimal("20.00"), reps=None, seconds=90
    )


@pytest.mark.parametrize(("reps", "seconds"), [(None, None), (5, 60)])
def test_set_needs_either_reps_or_seconds(reps, seconds):
    with pytest.raises(InvalidWorkout):
        SetEntry.create(None, reps=reps, seconds=seconds)


@pytest.mark.parametrize("seconds", [0, MAX_SECONDS + 1])
def test_timed_set_out_of_bounds(seconds):
    with pytest.raises(InvalidWorkout):
        SetEntry.create(None, seconds=seconds)


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
        ("BWx1:30", SetEntry(None, seconds=90)),
        ("32x45s", SetEntry(Decimal("32.00"), seconds=45)),
        ("bwx0:05", SetEntry(None, seconds=5)),
        ("BWx1:60", None),
        ("BWx0:00", None),
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


def _draft(sets: list[dict]) -> dict:
    return {
        "workout_date": "2026-01-01",
        "exercises": [{"exercise_id": 1, "exercise_name": "X", "sets": sets}],
    }


def test_timed_set_survives_fsm_draft():
    entry = SetEntry.create(None, seconds=90)
    sets = fsm_json.loads(fsm_json.dumps([set_to_fsm(entry)]))
    assert sets_from_fsm(sets) == [entry]
    assert build_record(1, _draft(sets)).exercises[0].sets == (entry,)


def test_drafts_started_before_timed_sets_still_load():
    """В подходах черновиков, начатых до обновления, нет ключа seconds."""
    sets = [{"weight": None, "reps": 10}]
    assert sets_from_fsm(sets) == [SetEntry(None, 10)]
    assert build_record(1, _draft(sets)).exercises[0].sets == (SetEntry(None, 10),)


def test_deleted_entry_keeps_name():
    entry = ExerciseEntry.deleted(" Old custom ", [SetEntry.create(None, 10)])
    assert (entry.exercise_id, entry.name) == (None, "Old custom")


@pytest.mark.parametrize(("name", "sets"), [("  ", [SetEntry(None, 10)]), ("Old", [])])
def test_deleted_entry_needs_name_and_sets(name, sets):
    with pytest.raises(InvalidWorkout):
        ExerciseEntry.deleted(name, sets)


BEFORE = LoggedWorkout(
    id=1,
    date=date(2026, 10, 30),
    notes=None,
    exercises=[
        LoggedExercise(7, "Bench Press", [SetEntry(Decimal("60.00"), 5)]),
        LoggedExercise(None, "Old custom", [SetEntry(None, 10)]),
    ],
)


def record(*entries):
    return WorkoutRecord.create(1, date(2026, 10, 30), None, list(entries))


def test_kept_deleted_exercise_allowed():
    check_deleted_entries(
        record(
            ExerciseEntry.create(7, [SetEntry(Decimal("60.00"), 5)]),
            ExerciseEntry.deleted("Old custom", [SetEntry(None, 12)]),
        ),
        BEFORE,
    )


def test_new_deleted_exercise_rejected():
    with pytest.raises(InvalidWorkout):
        check_deleted_entries(
            record(ExerciseEntry.deleted("Bench Press", [SetEntry(None, 5)])), BEFORE
        )
