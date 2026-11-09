from datetime import date, time
from decimal import Decimal

import pytest

from bot.workouts.domain import (
    ExerciseEntry,
    InvalidWorkout,
    LoggedExercise,
    LoggedWorkout,
    SetEntry,
)
from history_web.schemas import (
    record_from_json,
    workout_summary_to_json,
    workout_to_json,
)


def test_workout_to_json():
    w = LoggedWorkout(
        id=42,
        date=date(2026, 10, 30),
        notes="week 3",
        exercises=[
            LoggedExercise(
                7, "Bench Press", [SetEntry(Decimal("62.50"), 5)], notes="no bench"
            ),
            LoggedExercise(None, "Old custom", [SetEntry(None, seconds=60)]),
        ],
    )
    assert workout_to_json(w) == {
        "id": 42,
        "date": "2026-10-30",
        "notes": "week 3",
        "start_time": None,
        "end_time": None,
        "duration_minutes": None,
        "exercises": [
            {
                "exercise_id": 7,
                "name": "Bench Press",
                "notes": "no bench",
                "sets": [{"weight": 62.5, "reps": 5, "seconds": None}],
            },
            {
                "exercise_id": None,
                "name": "Old custom",
                "notes": None,
                "sets": [{"weight": None, "reps": None, "seconds": 60}],
            },
        ],
    }


def test_workout_time_to_json():
    w = LoggedWorkout(
        42, date(2026, 10, 30), None, [], start_time=time(23, 30), end_time=time(0, 45)
    )
    assert workout_summary_to_json(w) == {
        "id": 42,
        "date": "2026-10-30",
        "notes": None,
        "start_time": "23:30",
        "end_time": "00:45",
        "duration_minutes": 75,
    }


def test_record_from_json_builds_record():
    body = {
        "date": "2026-10-30",
        "notes": " week 3 ",
        "start_time": None,
        "end_time": None,
        "exercises": [
            {
                "exercise_id": 7,
                "notes": " no bench ",
                "sets": [{"weight": Decimal("62.5"), "reps": 5, "seconds": None}],
            },
            {
                "exercise_id": None,
                "name": "Old custom",
                "notes": None,
                "sets": [{"weight": None, "reps": None, "seconds": 60}],
            },
        ],
    }
    r = record_from_json(1, body)
    assert (r.user_id, r.date, r.notes) == (1, date(2026, 10, 30), "week 3")
    assert r.exercises[0] == ExerciseEntry(
        7, (SetEntry(Decimal("62.50"), 5, None),), notes="no bench"
    )
    assert r.exercises[1].notes is None
    assert (r.exercises[1].exercise_id, r.exercises[1].name) == (None, "Old custom")
    assert (r.start_time, r.end_time) == (None, None)


GOOD_SET = {"weight": None, "reps": 5, "seconds": None}


def body_with(exercise):
    return {
        "date": "2026-10-30",
        "start_time": None,
        "end_time": None,
        "exercises": [{"notes": None, **exercise}],
    }


def timed(start, end):
    body = body_with({"exercise_id": 7, "sets": [GOOD_SET]})
    return body | {"start_time": start, "end_time": end}


def test_record_from_json_takes_time():
    r = record_from_json(1, timed("18:05", "19:20"))
    assert (r.start_time, r.end_time) == (time(18, 5), time(19, 20))


TIME_REJECTS = [
    # старая страница из кэша: нет времени тренировки
    {
        "date": "2026-10-30",
        "exercises": [{"exercise_id": 7, "notes": None, "sets": [GOOD_SET]}],
    },
    timed("18:05", None),
    timed("18:5", "19:20"),
    timed("25:00", "19:20"),
    timed("18:05:00", "19:20"),
    timed(1805, "19:20"),
    timed("19:20", "18:05"),  # конец раньше начала — почти сутки
]


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"exercises": [{"exercise_id": 7, "sets": [GOOD_SET]}]},
        {"date": "30-10-2026", "exercises": [{"exercise_id": 7, "sets": [GOOD_SET]}]},
        {"date": "2026-10-30", "notes": 5, "exercises": []},
        {"date": "2026-10-30", "start_time": None, "end_time": None, "exercises": []},
        {"date": "2026-10-30", "exercises": {}},
        body_with({"exercise_id": 7, "sets": []}),
        body_with({"exercise_id": "7", "sets": [GOOD_SET]}),
        body_with({"exercise_id": None, "sets": [GOOD_SET]}),
        body_with({"exercise_id": 7}),
        body_with({"exercise_id": 7, "sets": [{**GOOD_SET, "reps": "5"}]}),
        body_with({"exercise_id": 7, "sets": [{**GOOD_SET, "reps": True}]}),
        body_with({"exercise_id": 7, "sets": [{**GOOD_SET, "weight": "abc"}]}),
        body_with({"exercise_id": 7, "sets": [{**GOOD_SET, "weight": 1000}]}),
        body_with({"exercise_id": 7, "sets": ["100x5"]}),
        # старая страница из кэша: нет notes у упражнения
        {"date": "2026-10-30", "exercises": [{"exercise_id": 7, "sets": [GOOD_SET]}]},
        body_with({"exercise_id": 7, "sets": [GOOD_SET], "notes": 5}),
        body_with({"exercise_id": 7, "sets": [GOOD_SET], "notes": "x" * 201}),
        *TIME_REJECTS,
    ],
)
def test_record_from_json_rejects(body):
    with pytest.raises(InvalidWorkout):
        record_from_json(1, body)


def test_empty_exercise_notes_become_none():
    body = body_with({"exercise_id": 7, "sets": [GOOD_SET], "notes": ""})
    assert record_from_json(1, body).exercises[0].notes is None
