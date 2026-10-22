from datetime import date
from decimal import Decimal

from bot.common.formatting import format_set_lines
from bot.export.prompt import build_ai_prompt
from bot.export.service import ExportExercise, ExportSet, ExportWorkout
from bot.workouts.domain import SetEntry


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
                    ExportSet(weight=Decimal("32.00"), reps=None, seconds=45),
                    ExportSet(weight=Decimal("32.00"), reps=None, seconds=75),
                ],
            )
        ],
    )
    prompt = build_ai_prompt([workout], "all time", None, date(2026, 1, 2))
    assert "  Farmer's Walk: 32x0:45, 32x1:15" in prompt.splitlines()
