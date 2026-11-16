from collections.abc import Sequence
from itertools import groupby

from bot.common.formatting import format_set_compact
from bot.programs.parser import PROGRAM_MARKER
from bot.workouts.domain import SetEntry


def _format_week(sets: Sequence[SetEntry]) -> str:
    """Одинаковые подходы подряд — одним «100x5x3», пустая неделя — «-»."""
    if not sets:
        return "-"
    parts = []
    for entry, same in groupby(sets):
        count = len(list(same))
        text = format_set_compact(entry)
        parts.append(f"{text}x{count}" if count > 1 else text)
    return ", ".join(parts)


def render_program(days: Sequence) -> str:
    """
    Программа в формате импорта — её можно прислать обратно как есть.

    days — PlanDay или StoredDay: нужны name и exercises с name, notes, weeks.
    """
    blocks = []
    for day in days:
        lines = [f"== {day.name} =="]
        for ex in day.exercises:
            line = f"{ex.name}: {' / '.join(_format_week(w) for w in ex.weeks)}"
            if ex.notes:
                line += f" | notes: {ex.notes}"
            lines.append(line)
        blocks.append("\n".join(lines))
    return f"{PROGRAM_MARKER}\n" + "\n\n".join(blocks)
