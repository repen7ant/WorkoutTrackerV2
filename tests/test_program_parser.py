from decimal import Decimal

import pytest

from bot.programs.domain import PlanDay, PlanExercise, ProgramPlan, sessions
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


def _ex(name, *weeks, notes=None) -> PlanExercise:
    return PlanExercise(name, tuple(tuple(week) for week in weeks), notes)


EXPECTED = ProgramPlan(
    days=(
        PlanDay(
            "Push",
            (
                _ex(
                    "Bench Press",
                    [
                        SetEntry(Decimal("100.00"), 5),
                        SetEntry(Decimal("102.50"), 5),
                        SetEntry(Decimal("102.50"), 4),
                    ],
                    notes="pause at the bottom",
                ),
                _ex("Dips", [SetEntry(None, 12)] * 2),
                _ex("Plank", [SetEntry(None, seconds=90)]),
            ),
        ),
        PlanDay("Pull", (_ex("Pull-ups", [SetEntry(None, 8)] * 3),)),
    ),
    weeks=1,
)

WEEKS = """# PROGRAM
== Push ==
Bench Press: 100x5x3 / 102.5x5x3 / 90x5x2 | notes: rest 3 min
Dips: BWx10x2, BWx8 / BWx12x3 / -
== Pull ==
Row: 60x10x3 / 62.5x10x3 / 55x10x2
"""

WEEKS_EXPECTED = ProgramPlan(
    days=(
        PlanDay(
            "Push",
            (
                _ex(
                    "Bench Press",
                    [SetEntry(Decimal("100.00"), 5)] * 3,
                    [SetEntry(Decimal("102.50"), 5)] * 3,
                    [SetEntry(Decimal("90.00"), 5)] * 2,
                    notes="rest 3 min",
                ),
                _ex(
                    "Dips",
                    [SetEntry(None, 10), SetEntry(None, 10), SetEntry(None, 8)],
                    [SetEntry(None, 12)] * 3,
                    [],
                ),
            ),
        ),
        PlanDay(
            "Pull",
            (
                _ex(
                    "Row",
                    [SetEntry(Decimal("60.00"), 10)] * 3,
                    [SetEntry(Decimal("62.50"), 10)] * 3,
                    [SetEntry(Decimal("55.00"), 10)] * 2,
                ),
            ),
        ),
    ),
    weeks=3,
)


def test_parse_one_week_is_old_format():
    assert parse_program(PROGRAM) == EXPECTED


def test_parse_weeks_with_counts_and_dash():
    assert parse_program(WEEKS) == WEEKS_EXPECTED


def test_parse_crlf_and_blank_lines():
    text = (
        "\r\n  # PROGRAM  \r\n\r\n"
        "==  Push  ==\r\n"
        "Bench Press:100x5,102.5x5,  102,5x4  |  notes:  pause at the bottom  \r\n"
        "Dips: BWx12 x 2\r\n"
        "Plank : BW x 1:30 \r\n"
        "\r\n\r\n"
        "== Pull ==\r\n"
        "Pull-ups: BWx8, BWx8, BWx8,\r\n"
    )
    assert parse_program(text) == EXPECTED


def test_parse_cyrillic_x_and_seconds():
    plan = parse_program("# PROGRAM\n== A ==\nPlank: BWх45s, 20Х1:00х2")
    assert plan.days[0].exercises[0].weeks == (
        (
            SetEntry(None, seconds=45),
            SetEntry(Decimal("20.00"), seconds=60),
            SetEntry(Decimal("20.00"), seconds=60),
        ),
    )


def test_parse_duplicate_exercise_in_day():
    plan = parse_program(
        "# PROGRAM\n== Push ==\nBench Press: 100x5\nDips: BWx10\nBench Press: 80x10"
    )
    assert [(ex.name, ex.weeks[0][0].reps) for ex in plan.days[0].exercises] == [
        ("Bench Press", 5),
        ("Dips", 10),
        ("Bench Press", 10),
    ]


def test_parse_colon_in_exercise_name():
    plan = parse_program("# PROGRAM\n== A ==\nRow: chest supported: 40x10 / 42.5x10")
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
            "too many sets in week 1 (max 10)",
        ),
        (
            "# PROGRAM\n== Push ==\nDips: BWx5 / BWx5x6, BWx5x5",
            3,
            "too many sets in week 2 (max 10)",
        ),
        (
            "# PROGRAM\n== Push ==\nDips: " + " / ".join(["BWx5"] * 13),
            3,
            "too many weeks (max 12)",
        ),
        (
            "# PROGRAM\n== Push ==\nBench: 100x5 / 100x5\nDips: BWx5",
            4,
            '"Dips" has 1 week, the program has 2',
        ),
        (
            "# PROGRAM\n== Push ==\nBench: 100x5 / 100x5\n== Pull ==\nRow: 1x1 / - / -",
            5,
            '"Row" has 3 weeks, the program has 2',
        ),
        ("# PROGRAM\n== Push ==\nDips: - / -", 3, "exercise has no sets in any week"),
        (
            "# PROGRAM\n== Push ==\nDips: BWx5 /  / BWx5",
            3,
            'week 2 has no sets (use "-" to skip a week)',
        ),
        (
            "# PROGRAM\n== Push ==\nBench Press:",
            3,
            'week 1 has no sets (use "-" to skip a week)',
        ),
        ("# PROGRAM\n== Push ==\nBench: 100x5x0", 3, 'invalid set count "100x5x0"'),
        ("# PROGRAM\n== Push ==\nBench: 100x5x11", 3, 'invalid set count "100x5x11"'),
        ("# PROGRAM\n== Push ==\nBench Press: 100x", 3, 'can\'t parse set "100x"'),
        (
            "# PROGRAM\n== Push ==\nBench Press: 100x5, 100x8-12",
            3,
            'can\'t parse set "100x8-12"',
        ),
        ("# PROGRAM\n== Push ==\nBench Press: 1000x5", 3, 'invalid set "1000x5"'),
        ("# PROGRAM\n== Push ==\nBench Press: 100x0", 3, 'invalid set "100x0"'),
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
        "Dips: BWx12x2\n"
        "Plank: BWx1:30\n"
        "\n"
        "== Pull ==\n"
        "Pull-ups: BWx8x3"
    )


def test_render_compresses_weeks():
    assert render_program(WEEKS_EXPECTED.days) == (
        "# PROGRAM\n"
        "== Push ==\n"
        "Bench Press: 100x5x3 / 102.5x5x3 / 90x5x2 | notes: rest 3 min\n"
        "Dips: BWx10x2, BWx8 / BWx12x3 / -\n"
        "\n"
        "== Pull ==\n"
        "Row: 60x10x3 / 62.5x10x3 / 55x10x2"
    )


@pytest.mark.parametrize("plan", [EXPECTED, WEEKS_EXPECTED])
def test_render_round_trip(plan):
    assert parse_program(render_program(plan.days)) == plan


def test_sessions_skip_empty_day_week():
    """Pull на неделе 2 и Push на неделе 3 без подходов — таких сессий нет."""
    plan = parse_program(
        "# PROGRAM\n== Push ==\nBench: 100x5 / 100x5 / -\n"
        "== Pull ==\nRow: 60x10 / - / 60x10"
    )
    assert sessions(plan.days, plan.weeks) == [(1, 1), (1, 2), (2, 1), (3, 2)]
