from datetime import date
from typing import Any

from bot.common.formatting import format_set_lines
from bot.workouts.domain import LoggedWorkout, SetEntry
from bot.workouts.draft import sets_from_fsm


def format_workout_main(exercises: list[dict[str, Any]]) -> str:
    if not exercises:
        return "Workout started. Add your first exercise."
    lines = ["<b>Current workout:</b>\n"]
    for ex in exercises:
        lines.append(f"<b>{ex['exercise_name']}</b>")
        lines.extend(format_set_lines(sets_from_fsm(ex["sets"])))
        lines.append("")
    return "\n".join(lines)


def format_current_sets(sets: list[SetEntry]) -> str:
    lines = ["<b>Current workout:</b>\n", *format_set_lines(sets, indent="")]
    return "\n".join(lines) + "\n\nEnter next set or finish exercise:"


def format_exercise_log(exercise_name: str, workouts: list[LoggedWorkout]) -> str:
    if not workouts:
        return f"<b>{exercise_name}</b>\n\nNo history yet."

    lines = [f"<b>{exercise_name}</b>\n"]
    for workout in workouts:
        lines.append(f"<b>{workout.date.strftime('%d-%m-%y')}</b>")
        if workout.notes:
            lines.append(f"<i>{workout.notes}</i>")
        for ex in workout.exercises:
            lines.extend(format_set_lines(ex.sets))
        lines.append("")
    return "\n".join(lines)


def format_confirm(data: dict[str, Any]) -> str:
    workout_date_raw = data.get("workout_date")
    workout_date = (
        date.fromisoformat(workout_date_raw).strftime("%d-%m-%y")
        if workout_date_raw
        else "—"
    )
    notes = data.get("notes") or "—"
    return f"<b>Date:</b> {workout_date}\n<b>Notes:</b> {notes}\n\nSave workout?"
