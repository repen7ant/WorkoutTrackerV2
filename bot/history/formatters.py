from bot.common.formatting import format_set_lines
from bot.workouts.domain import LoggedWorkout


def format_workout_detail(workout: LoggedWorkout) -> str:
    lines = [f"<b>{workout.date.strftime('%d-%m-%y')}</b>"]
    if workout.notes:
        lines.append(f"<i>{workout.notes}</i>")
    lines.append("")
    for ex in workout.exercises:
        lines.append(f"<b>{ex.name}</b>")
        lines.extend(format_set_lines(ex.sets))
        lines.append("")
    return "\n".join(lines)
