from datetime import date
from typing import Any

from bot.common.formatting import escape, format_set_lines
from bot.workouts.domain import LoggedWorkout, SetEntry
from bot.workouts.draft import sets_from_fsm


def format_workout_main(exercises: list[dict[str, Any]]) -> str:
    if not exercises:
        return "Workout started. Add your first exercise."
    lines = ["<b>Current workout:</b>\n"]
    for ex in exercises:
        lines.append(f"<b>{escape(ex['exercise_name'])}</b>")
        # у черновиков, начатых до заметок к упражнениям, ключа нет
        if ex.get("notes"):
            lines.append(f"<i>{escape(ex['notes'])}</i>")
        lines.extend(format_set_lines(sets_from_fsm(ex["sets"])))
        lines.append("")
    return "\n".join(lines)


def format_current_sets(
    exercise_name: str, notes: str | None, sets: list[SetEntry]
) -> str:
    lines = [f"<b>{escape(exercise_name)}</b>"]
    if notes:
        lines.append(f"<i>{escape(notes)}</i>")
    lines.append("")
    if sets:
        lines.extend([*format_set_lines(sets, indent=""), ""])
    lines.append("Enter next set, a note, or finish exercise:")
    return "\n".join(lines)


def format_exercise_log(exercise_name: str, workouts: list[LoggedWorkout]) -> str:
    if not workouts:
        return f"<b>{escape(exercise_name)}</b>\n\nNo history yet."

    lines = [f"<b>{escape(exercise_name)}</b>\n"]
    for workout in workouts:
        lines.append(f"<b>{workout.date.strftime('%d-%m-%y')}</b>")
        for ex in workout.exercises:
            if ex.notes:
                lines.append(f"<i>{escape(ex.notes)}</i>")
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
    notes = escape(data["notes"]) if data.get("notes") else "—"
    return f"<b>Date:</b> {workout_date}\n<b>Notes:</b> {notes}\n\nSave workout?"
