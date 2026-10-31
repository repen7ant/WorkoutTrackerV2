from datetime import date
from decimal import Decimal

import pytest

from bot.workouts.domain import (
    ExerciseEntry,
    InvalidWorkout,
    LoggedExercise,
    LoggedWorkout,
    SetEntry,
)
from history_web.schemas import record_from_json, workout_to_json


def test_workout_to_json():
    w = LoggedWorkout(
        id=42,
        date=date(2026, 10, 30),
        notes="week 3",
        exercises=[
            LoggedExercise(7, "Bench Press", [SetEntry(Decimal("62.50"), 5)]),
            LoggedExercise(None, "Old custom", [SetEntry(None, seconds=60)]),
        ],
    )
    assert workout_to_json(w) == {
        "id": 42,
        "date": "2026-10-30",
        "notes": "week 3",
        "exercises": [
            {
                "exercise_id": 7,
                "name": "Bench Press",
                "sets": [{"weight": 62.5, "reps": 5, "seconds": None}],
            },
            {
                "exercise_id": None,
                "name": "Old custom",
                "sets": [{"weight": None, "reps": None, "seconds": 60}],
            },
        ],
    }


def test_record_from_json_builds_record():
    body = {
        "date": "2026-10-30",
        "notes": " week 3 ",
        "exercises": [
            {
                "exercise_id": 7,
                "sets": [{"weight": Decimal("62.5"), "reps": 5, "seconds": None}],
            },
            {
                "exercise_id": None,
                "name": "Old custom",
                "sets": [{"weight": None, "reps": None, "seconds": 60}],
            },
        ],
    }
    r = record_from_json(1, body)
    assert (r.user_id, r.date, r.notes) == (1, date(2026, 10, 30), "week 3")
    assert r.exercises[0] == ExerciseEntry(7, (SetEntry(Decimal("62.50"), 5, None),))
    assert (r.exercises[1].exercise_id, r.exercises[1].name) == (None, "Old custom")


GOOD_SET = {"weight": None, "reps": 5, "seconds": None}


def body_with(exercise):
    return {"date": "2026-10-30", "exercises": [exercise]}


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"exercises": [{"exercise_id": 7, "sets": [GOOD_SET]}]},
        {"date": "30-10-2026", "exercises": [{"exercise_id": 7, "sets": [GOOD_SET]}]},
        {"date": "2026-10-30", "notes": 5, "exercises": []},
        {"date": "2026-10-30", "exercises": []},
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
    ],
)
def test_record_from_json_rejects(body):
    with pytest.raises(InvalidWorkout):
        record_from_json(1, body)
