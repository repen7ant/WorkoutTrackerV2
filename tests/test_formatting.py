from datetime import date
from decimal import Decimal

from bot.catalog.formatters import format_exercise_list
from bot.catalog.models import Exercise, Muscle
from bot.common.formatting import format_set_lines
from bot.export.prompt import build_ai_prompt
from bot.export.service import ExportExercise, ExportWorkout
from bot.history.formatters import format_workout_detail
from bot.workouts.domain import LoggedExercise, LoggedWorkout, SetEntry
from bot.workouts.formatters import (
    format_confirm,
    format_exercise_log,
    format_workout_main,
)

NASTY = "<3 & co"
SAFE = "&lt;3 &amp; co"
NASTY_WORKOUT = LoggedWorkout(
    1, date(2026, 1, 1), NASTY, [LoggedExercise(7, NASTY, [SetEntry(None, 5)])]
)


def test_timed_sets_shown_as_minutes_and_seconds():
    sets = [
        SetEntry.create(None, seconds=90),
        SetEntry.create(Decimal("20"), seconds=5),
    ]
    assert format_set_lines(sets) == ["  1. BW x 1:30", "  2. 20.00kg x 0:05"]


def test_export_shows_timed_sets():
    workout = ExportWorkout(
        date=date(2026, 1, 1),
        notes=None,
        exercises=[
            ExportExercise(
                name="Farmer's Walk",
                muscles=[],
                sets=[
                    SetEntry.create(Decimal("32"), seconds=45),
                    SetEntry.create(Decimal("32"), seconds=75),
                ],
            )
        ],
    )
    prompt = build_ai_prompt([workout], "all time", None, date(2026, 1, 2))
    assert "  Farmer's Walk: 32x0:45, 32x1:15" in prompt.splitlines()


def test_workout_detail_escapes_user_text():
    text = format_workout_detail(NASTY_WORKOUT)
    assert f"<i>{SAFE}</i>" in text
    assert f"<b>{SAFE}</b>" in text


def test_exercise_log_escapes_user_text():
    text = format_exercise_log(NASTY, [NASTY_WORKOUT])
    assert text.startswith(f"<b>{SAFE}</b>")
    assert NASTY not in text
    assert format_exercise_log(NASTY, []).startswith(f"<b>{SAFE}</b>")


def test_workout_main_escapes_exercise_name():
    text = format_workout_main(
        [{"exercise_name": NASTY, "sets": [{"weight": None, "reps": 5}]}]
    )
    assert f"<b>{SAFE}</b>" in text


def test_confirm_escapes_notes():
    data = {"workout_date": "2026-01-01", "notes": NASTY}
    assert f"<b>Notes:</b> {SAFE}" in format_confirm(data)


def test_exercise_list_escapes_names_and_muscles():
    text = format_exercise_list([Exercise(name=NASTY, muscles=[Muscle(name=NASTY)])])
    assert f"1. {SAFE}\n   {SAFE}" in text
