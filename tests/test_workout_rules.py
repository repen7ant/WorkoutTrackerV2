from datetime import UTC, date, datetime, time
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
    duration_minutes,
    exercise_notes,
)
from bot.workouts.draft import (
    build_record,
    minutes_since_start,
    set_to_fsm,
    sets_from_fsm,
    utc_now_iso,
    workout_times,
)
from bot.workouts.handlers.recording import is_note, parse_set
from bot.workouts.service import check_deleted_entries

CYR_X = "\u0445"  # русская «х»
CYR_S = "\u0441"  # русская «с» — секунды


@pytest.mark.parametrize(
    ("weight", "reps"),
    [
        (None, 0),
        (None, MAX_REPS + 1),
        (Decimal("-1"), 5),
        (Decimal("NaN"), 5),
        (Decimal("Infinity"), 5),
        (Decimal("999.995"), 5),  # после округления — 1000.00
        (Decimal("1" * 27), 5),  # не влезает в точность Decimal при округлении
        (Decimal("1e30"), 5),
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
        ("100" + CYR_X + "5", SetEntry(Decimal("100.00"), 5)),
        ("100" + CYR_X.upper() + "5", SetEntry(Decimal("100.00"), 5)),
        ("82,5x5", SetEntry(Decimal("82.50"), 5)),
        ("BW" + CYR_X + "1:30", SetEntry(None, seconds=90)),
        ("82,5,5x5", None),
        ("BWx45" + CYR_S, SetEntry(None, seconds=45)),
        ("20" + CYR_X + "45" + CYR_S.upper(), SetEntry(Decimal("20.00"), seconds=45)),
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
        build_record(1, data, 180)


def _draft(sets: list[dict]) -> dict:
    return {
        "workout_date": "2026-01-01",
        "exercises": [{"exercise_id": 1, "exercise_name": "X", "sets": sets}],
    }


def test_timed_set_survives_fsm_draft():
    entry = SetEntry.create(None, seconds=90)
    sets = fsm_json.loads(fsm_json.dumps([set_to_fsm(entry)]))
    assert sets_from_fsm(sets) == [entry]
    assert build_record(1, _draft(sets), 180).exercises[0].sets == (entry,)


def test_drafts_started_before_timed_sets_still_load():
    """В подходах черновиков, начатых до обновления, нет ключа seconds."""
    sets = [{"weight": None, "reps": 10}]
    assert sets_from_fsm(sets) == [SetEntry(None, 10)]
    assert build_record(1, _draft(sets), 180).exercises[0].sets == (SetEntry(None, 10),)


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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        (" no bench ", "no bench"),
        ("x" * 200, "x" * 200),
    ],
)
def test_exercise_notes_cleaned(text, expected):
    assert exercise_notes(text) == expected


def test_exercise_notes_too_long():
    with pytest.raises(InvalidWorkout):
        exercise_notes("x" * 201)


def test_entries_keep_notes():
    sets = [SetEntry.create(None, 5)]
    assert ExerciseEntry.create(7, sets, " no bench ").notes == "no bench"
    assert ExerciseEntry.deleted("Old", sets, "sore").notes == "sore"
    assert ExerciseEntry.create(7, sets).notes is None


def test_entry_rejects_long_notes():
    with pytest.raises(InvalidWorkout):
        ExerciseEntry.create(7, [SetEntry.create(None, 5)], "x" * 201)


def test_build_record_keeps_exercise_notes():
    data = _draft([{"weight": None, "reps": 10}])
    data["exercises"][0]["notes"] = "no bench"
    assert build_record(1, data, 180).exercises[0].notes == "no bench"


def test_drafts_started_before_notes_still_load():
    """У упражнений в черновиках, начатых до обновления, нет ключа notes."""
    record = build_record(1, _draft([{"weight": None, "reps": 10}]), 180)
    assert record.exercises[0].notes is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("плечо болит", True),
        ("no bench, did floor press", True),
        ("100kg x 5", True),
        ("100x5", False),
        ("100" + CYR_X + "5", False),
        ("82,5x5", False),
        ("100 5", False),
        ("100x", False),
        ("100*5", False),
        ("BWx1:30", False),
        ("bwx10", False),
        ("20x45s", False),
        ("BWx45" + CYR_S, False),
        ("", False),
        (None, False),
    ],
)
def test_is_note(text, expected):
    assert is_note(text) is expected


def _timed(
    started="2026-11-09T15:05:40+00:00",
    finished="2026-11-09T16:20:10+00:00",
    day="2026-11-09",
):
    return {"started_at": started, "finished_at": finished, "workout_date": day}


NIGHT = ("2026-11-09T20:30:00+00:00", "2026-11-09T21:45:00+00:00")


@pytest.mark.parametrize(
    ("data", "offset", "expected"),
    [
        (_timed(), 180, (time(18, 5), time(19, 20))),  # секунды отброшены
        (_timed(), -600, (time(5, 5), time(6, 20))),
        # 23:30–00:45 по Москве: подходит и день начала, и день конца
        (_timed(*NIGHT, "2026-11-09"), 180, (time(23, 30), time(0, 45))),
        (_timed(*NIGHT, "2026-11-10"), 180, (time(23, 30), time(0, 45))),
        (_timed(day="2026-11-01"), 180, None),  # дату ввели вручную
        (_timed(finished="2026-11-09T21:06:00+00:00"), 180, None),  # дольше 6 ч
        (_timed(finished="2026-11-09T15:00:00+00:00"), 180, None),  # конец раньше
        # черновик, начатый до обновления
        ({"workout_date": "2026-11-09", "finished_at": NIGHT[1]}, 180, None),
        ({"workout_date": "2026-11-09", "started_at": NIGHT[0]}, 180, None),
    ],
)
def test_workout_times(data, offset, expected):
    assert workout_times(data, offset) == expected


@pytest.mark.parametrize(
    ("start", "end", "minutes"),
    [
        (time(18, 5), time(19, 20), 75),
        (time(23, 30), time(0, 45), 75),
        (time(18, 5), time(18, 5), 0),
    ],
)
def test_duration_minutes(start, end, minutes):
    assert duration_minutes(start, end) == minutes


def test_workout_time_needs_both_ends():
    bench = ExerciseEntry.create(7, [SetEntry.create(None, 5)])
    with pytest.raises(InvalidWorkout):
        WorkoutRecord.create(1, date(2026, 1, 1), None, [bench], start_time=time(18, 5))


def test_build_record_takes_workout_time():
    data = _draft([{"weight": None, "reps": 10}]) | _timed()
    record = build_record(1, data, 180)
    assert (record.start_time, record.end_time) == (time(18, 5), time(19, 20))


def test_draft_moments_survive_redis():
    data = {"started_at": utc_now_iso()}
    assert fsm_json.loads(fsm_json.dumps(data)) == data


@pytest.mark.parametrize(
    ("data", "minutes"),
    [
        ({"started_at": "2026-11-09T15:05:40+00:00"}, 44),
        ({"started_at": "2026-11-09T15:51:00+00:00"}, 0),  # часы чуть разошлись
        ({}, None),
    ],
)
def test_minutes_since_start(data, minutes):
    now = datetime(2026, 11, 9, 15, 50, 39, tzinfo=UTC)
    assert minutes_since_start(data, now) == minutes
