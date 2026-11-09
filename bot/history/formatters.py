from bot.common.formatting import escape, format_set_lines, format_workout_time
from bot.workouts.domain import LoggedWorkout


def format_workout_detail(workout: LoggedWorkout) -> str:
    when = format_workout_time(workout.start_time, workout.end_time)
    lines = [f"<b>{workout.date.strftime('%d-%m-%y')}</b>{when}"]
    if workout.notes:
        lines.append(f"<i>{escape(workout.notes)}</i>")
    lines.append("")
    for ex in workout.exercises:
        lines.append(f"<b>{escape(ex.name)}</b>")
        if ex.notes:
            lines.append(f"<i>{escape(ex.notes)}</i>")
        lines.extend(format_set_lines(ex.sets))
        lines.append("")
    return "\n".join(lines)
