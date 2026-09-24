from collections.abc import Iterable

from bot.workouts.domain import SetEntry


def format_weight(weight) -> str:
    return "BW" if weight is None else f"{weight}kg"


def format_set_lines(sets: Iterable[SetEntry], indent: str = "  ") -> list[str]:
    return [
        f"{indent}{i}. {format_weight(s.weight)} x {s.reps}"
        for i, s in enumerate(sets, start=1)
    ]
