import html
from collections.abc import Iterable
from datetime import time

from bot.workouts.domain import SetEntry, duration_minutes


def escape(text: str) -> str:
    """Текст пользователя для сообщений с parse_mode="HTML"."""
    return html.escape(text, quote=False)


def format_weight(weight) -> str:
    return "BW" if weight is None else f"{weight}kg"


def format_amount(entry: SetEntry) -> str:
    """Повторения или время подхода (мин:сек)."""
    if entry.seconds is None:
        return str(entry.reps)
    minutes, secs = divmod(entry.seconds, 60)
    return f"{minutes}:{secs:02d}"


def format_set_lines(sets: Iterable[SetEntry], indent: str = "  ") -> list[str]:
    return [
        f"{indent}{i}. {format_weight(s.weight)} x {format_amount(s)}"
        for i, s in enumerate(sets, start=1)
    ]


def format_duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if not hours:
        return f"{mins} min"
    return f"{hours} h {mins} min" if mins else f"{hours} h"


def format_workout_time(start: time | None, end: time | None) -> str:
    """То, что идёт после даты тренировки; без времени — пусто."""
    if start is None or end is None:
        return ""
    duration = format_duration(duration_minutes(start, end))
    return f" · {start:%H:%M}–{end:%H:%M} ({duration})"
