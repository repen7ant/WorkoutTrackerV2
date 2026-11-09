from datetime import date, time
from decimal import Decimal

import pytest

from bot.catalog.formatters import format_exercise_list
from bot.catalog.models import Exercise, Muscle
from bot.common.formatting import (
    format_duration,
    format_set_lines,
    format_workout_time,
)
from bot.export.prompt import build_ai_prompt
from bot.export.service import ExportExercise, ExportWorkout
from bot.history.formatters import format_workout_detail
from bot.workouts.domain import LoggedExercise, LoggedWorkout, SetEntry
from bot.workouts.formatters import (
    format_confirm,
    format_current_sets,
    format_exercise_log,
    format_sets_prompt,
    format_workout_main,
)
from bot.workouts.keyboards import set_entered_kb

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
                notes=None,
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


FOOTER = "Enter next set, a note, or finish exercise:"
SETS = [SetEntry.create(Decimal("100"), 5)] * 2


def test_current_sets_show_name_notes_and_sets():
    assert format_current_sets("Bench Press", "<no bench>", SETS) == (
        "<b>Bench Press</b>\n<i>&lt;no bench&gt;</i>\n\n"
        "1. 100.00kg x 5\n2. 100.00kg x 5\n\n" + FOOTER
    )


def test_current_sets_without_notes():
    assert format_current_sets("Bench Press", None, SETS[:1]) == (
        "<b>Bench Press</b>\n\n1. 100.00kg x 5\n\n" + FOOTER
    )


def test_current_sets_notes_before_first_set():
    assert format_current_sets("Bench Press", "no bench", []) == (
        "<b>Bench Press</b>\n<i>no bench</i>\n\n" + FOOTER
    )


def test_workout_main_shows_exercise_notes():
    text = format_workout_main(
        [
            {
                "exercise_name": "Bench Press",
                "notes": "no bench",
                "sets": [{"weight": None, "reps": 5}],
            },
            # черновик, начатый до обновления
            {"exercise_name": "Squat", "sets": [{"weight": None, "reps": 5}]},
        ]
    )
    assert "<b>Bench Press</b>\n<i>no bench</i>\n  1. BW x 5" in text
    assert "<b>Squat</b>\n  1. BW x 5" in text


def test_remove_note_button_only_with_notes():
    def callbacks(kb):
        return [b.callback_data for row in kb.inline_keyboard for b in row]

    assert "wk_remove_note" in callbacks(set_entered_kb(has_notes=True))
    assert "wk_remove_note" not in callbacks(set_entered_kb())


WORKOUT = LoggedWorkout(
    1,
    date(2026, 1, 1),
    "week 3",
    [LoggedExercise(7, "Bench Press", [SetEntry(None, 5)], notes="<no bench>")],
)


def test_exercise_log_shows_exercise_notes_instead_of_workout_notes():
    text = format_exercise_log("Bench Press", [WORKOUT])
    assert "week 3" not in text
    assert "<b>01-01-26</b>\n<i>&lt;no bench&gt;</i>\n  1. BW x 5" in text


def test_workout_detail_shows_both_notes():
    text = format_workout_detail(WORKOUT)
    assert text.startswith("<b>01-01-26</b>\n<i>week 3</i>")
    assert "<b>Bench Press</b>\n<i>&lt;no bench&gt;</i>\n  1. BW x 5" in text


def test_export_keeps_notes_on_one_line():
    workout = ExportWorkout(
        date=date(2026, 1, 1),
        notes="bad\nsleep",
        exercises=[
            ExportExercise(
                name="Bench Press",
                muscles=[],
                sets=[SetEntry.create(Decimal("100"), 5)],
                notes="no bench,\nfloor press",
            )
        ],
    )
    lines = build_ai_prompt([workout], "all time", None, date(2026, 1, 2)).splitlines()
    assert "2026-01-01 | notes: bad sleep" in lines
    assert "  Bench Press: 100x5 | notes: no bench, floor press" in lines


SETS_PROMPT = (
    "Enter set (e.g. <code>100x5</code>, <code>BWx10</code>"
    " or time <code>BWx1:30</code> / <code>BWx90s</code>)"
    " or any text to add a note:"
)


def test_sets_prompt_without_name():
    assert format_sets_prompt() == SETS_PROMPT


def test_sets_prompt_starts_with_escaped_name():
    assert format_sets_prompt(NASTY) == f"<b>{SAFE}</b>\n\n{SETS_PROMPT}"


@pytest.mark.parametrize(
    ("minutes", "text"),
    [(0, "0 min"), (45, "45 min"), (60, "1 h"), (75, "1 h 15 min"), (600, "10 h")],
)
def test_format_duration(minutes, text):
    assert format_duration(minutes) == text


def test_format_workout_time():
    assert format_workout_time(time(23, 30), time(0, 45)) == (
        " · 23:30–00:45 (1 h 15 min)"
    )
    assert format_workout_time(None, None) == ""
