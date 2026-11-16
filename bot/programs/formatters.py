from collections.abc import Sequence

from bot.common.formatting import format_set_compact
from bot.programs.parser import PROGRAM_MARKER


def render_program(days: Sequence) -> str:
    """
    Программа в формате импорта — её можно прислать обратно как есть.

    days — PlanDay или StoredDay: нужны name и exercises с name, notes, sets.
    """
    blocks = []
    for day in days:
        lines = [f"== {day.name} =="]
        for ex in day.exercises:
            line = f"{ex.name}: {', '.join(format_set_compact(s) for s in ex.sets)}"
            if ex.notes:
                line += f" | notes: {ex.notes}"
            lines.append(line)
        blocks.append("\n".join(lines))
    return f"{PROGRAM_MARKER}\n" + "\n\n".join(blocks)
