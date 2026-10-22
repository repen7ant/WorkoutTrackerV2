from collections.abc import Iterable

from bot.workouts.domain import SetEntry


def format_weight(weight) -> str:
    return "BW" if weight is None else f"{weight}kg"


def format_amount(reps: int | None, seconds: int | None) -> str:
    """Повторения или время подхода (мин:сек)."""
    if seconds is None:
        return str(reps)
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}:{secs:02d}"


def format_set_lines(sets: Iterable[SetEntry], indent: str = "  ") -> list[str]:
    return [
        f"{indent}{i}. {format_weight(s.weight)} x {format_amount(s.reps, s.seconds)}"
        for i, s in enumerate(sets, start=1)
    ]
