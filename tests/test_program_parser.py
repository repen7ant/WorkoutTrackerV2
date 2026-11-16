from decimal import Decimal

import pytest

from bot.programs.domain import (
    PlanDay,
    PlanExercise,
    ProgramPlan,
    next_after,
)
from bot.programs.formatters import render_program
from bot.programs.parser import ProgramParseError, parse_program
from bot.workouts.domain import SetEntry

PROGRAM = """# PROGRAM
== Push ==
Bench Press: 100x5, 102.5x5, 102,5x4 | notes: pause at the bottom
Dips: BWx12, BWx12
Plank: BWx1:30
== Pull ==
Pull-ups: BWx8, BWx8, BWx8
"""

EXPECTED = ProgramPlan(
    days=(
        PlanDay(
            "Push",
            (
                PlanExercise(
                    "Bench Press",
                    (
                        SetEntry(Decimal("100.00"), 5),
                        SetEntry(Decimal("102.50"), 5),
                        SetEntry(Decimal("102.50"), 4),
                    ),
                    "pause at the bottom",
                ),
                PlanExercise("Dips", (SetEntry(None, 12), SetEntry(None, 12)), None),
                PlanExercise("Plank", (SetEntry(None, seconds=90),), None),
            ),
        ),
        PlanDay(
            "Pull",
            (PlanExercise("Pull-ups", (SetEntry(None, 8),) * 3, None),),
        ),
    )
)


def test_parse_valid_program():
    assert parse_program(PROGRAM) == EXPECTED


def test_parse_crlf_and_blank_lines():
    text = (
        "\r\n  # PROGRAM  \r\n\r\n"
        "==  Push  ==\r\n"
        "Bench Press:100x5,102.5x5,  102,5x4  |  notes:  pause at the bottom  \r\n"
        "Dips: BWx12, BWx12\r\n"
        "Plank : BW x 1:30 \r\n"
        "\r\n\r\n"
        "== Pull ==\r\n"
        "Pull-ups: BWx8, BWx8, BWx8,\r\n"
    )
    assert parse_program(text) == EXPECTED


def test_parse_cyrillic_x_and_seconds():
    plan = parse_program("# PROGRAM\n== A ==\nPlank: BWх45s, 20Х1:00")
    assert plan.days[0].exercises[0].sets == (
        SetEntry(None, seconds=45),
        SetEntry(Decimal("20.00"), seconds=60),
    )


def test_parse_duplicate_exercise_in_day():
    plan = parse_program(
        "# PROGRAM\n== Push ==\nBench Press: 100x5\nDips: BWx10\nBench Press: 80x10"
    )
    assert [(ex.name, ex.sets[0].reps) for ex in plan.days[0].exercises] == [
        ("Bench Press", 5),
        ("Dips", 10),
        ("Bench Press", 10),
    ]


def test_parse_colon_in_exercise_name():
    plan = parse_program("# PROGRAM\n== A ==\nRow: chest supported: 40x10")
    assert plan.days[0].exercises[0].name == "Row: chest supported"


def _days(count: int) -> str:
    return "".join(f"== Day {i} ==\nDips: BWx5\n" for i in range(1, count + 1))


@pytest.mark.parametrize(
    ("text", "line", "reason"),
    [
        ("== Push ==\nDips: BWx5", 1, 'first line must be "# PROGRAM"'),
        ("", 1, 'first line must be "# PROGRAM"'),
        ("# PROGRAM\n", 1, "program has no days"),
        ("# PROGRAM\nDips: BWx5", 2, "exercise before the first day"),
        (
            "# PROGRAM\n== Push ==\n== Pull ==\nDips: BWx5",
            2,
            'day "Push" has no exercises',
        ),
        (
            "# PROGRAM\n== Push ==\nDips: BWx5\n== push ==\nDips: BWx5",
            4,
            'duplicate day "push"',
        ),
        ("# PROGRAM\n== ==\nDips: BWx5", 2, "day name is empty"),
        (
            "# PROGRAM\n== " + "A" * 33 + " ==\nDips: BWx5",
            2,
            "day name is too long (max 32 characters)",
        ),
        ("# PROGRAM\n" + _days(11), 22, "too many days (max 10)"),
        (
            "# PROGRAM\n== Push ==\n" + "Dips: BWx5\n" * 13,
            2,
            'day "Push" has too many exercises (max 12)',
        ),
        (
            "# PROGRAM\n== Push ==\nDips: " + ", ".join(["BWx5"] * 11),
            3,
            "too many sets (max 10)",
        ),
        ("# PROGRAM\n== Push ==\nBench Press: 100x", 3, 'can\'t parse set "100x"'),
        (
            "# PROGRAM\n== Push ==\nBench Press: 100x5, 100x8-12",
            3,
            'can\'t parse set "100x8-12"',
        ),
        ("# PROGRAM\n== Push ==\nBench Press: 1000x5", 3, 'invalid set "1000x5"'),
        ("# PROGRAM\n== Push ==\nBench Press: 100x0", 3, 'invalid set "100x0"'),
        ("# PROGRAM\n== Push ==\nBench Press:", 3, "exercise has no sets"),
        (
            "# PROGRAM\n== Push ==\nGood luck!",
            3,
            'expected "Exercise: sets", got "Good luck!"',
        ),
        (": 100x5", 1, 'first line must be "# PROGRAM"'),
        ("# PROGRAM\n== Push ==\n: 100x5", 3, "exercise name is empty"),
        (
            "# PROGRAM\n== Push ==\n" + "A" * 129 + ": 100x5",
            3,
            "exercise name is too long (max 128 characters)",
        ),
        (
            "# PROGRAM\n== Push ==\nBench Press: 100x5 | pause",
            3,
            'expected "| notes: ..." after the sets',
        ),
        (
            "# PROGRAM\n== Push ==\nBench Press: 100x5 | notes: " + "a" * 201,
            3,
            "notes are too long (max 200 characters)",
        ),
    ],
)
def test_parse_errors(text, line, reason):
    with pytest.raises(ProgramParseError) as exc:
        parse_program(text)
    assert (exc.value.line, exc.value.reason) == (line, reason)


def test_parse_error_message():
    text = "# PROGRAM\n== Push ==\nDips: BWx5\n\n== Pull ==\nRows: 60x10\nBench 100 5"
    with pytest.raises(ProgramParseError) as exc:
        parse_program(text)
    assert str(exc.value) == 'line 7: expected "Exercise: sets", got "Bench 100 5"'


def test_render_program():
    assert render_program(EXPECTED.days) == (
        "# PROGRAM\n"
        "== Push ==\n"
        "Bench Press: 100x5, 102.5x5, 102.5x4 | notes: pause at the bottom\n"
        "Dips: BWx12, BWx12\n"
        "Plank: BWx1:30\n"
        "\n"
        "== Pull ==\n"
        "Pull-ups: BWx8, BWx8, BWx8"
    )


def test_render_round_trip():
    assert parse_program(render_program(EXPECTED.days)) == EXPECTED


@pytest.mark.parametrize(
    ("position", "count", "expected"), [(1, 3, 2), (2, 3, 3), (3, 3, 1), (1, 1, 1)]
)
def test_next_after(position, count, expected):
    assert next_after(position, count) == expected
