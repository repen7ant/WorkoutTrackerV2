import pytest

from bot.catalog.api import parse_muscle_names


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Chest, Tricep", ["Chest", "Tricep"]),
        ("  Chest  ", ["Chest"]),
        ("Chest, ", ["Chest"]),
        ("Chest,,Tricep", ["Chest", "Tricep"]),
        ("—", []),
        ("-", []),
    ],
)
def test_parse_muscle_names(text, expected):
    assert parse_muscle_names(text) == expected
