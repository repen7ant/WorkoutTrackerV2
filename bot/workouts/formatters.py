from datetime import date
from typing import Any

from bot.common.formatting import escape, format_duration, format_set_lines
from bot.workouts.domain import LoggedWorkout, SetEntry
from bot.workouts.draft import sets_from_fsm


def format_workout_main(
    exercises: list[dict[str, Any]], elapsed_minutes: int | None = None
) -> str:
    if not exercises:
        return "Workout started. Add your first exercise."
    # у черновиков, начатых до обновления, начала нет
    if elapsed_minutes is None:
        title = "<b>Current workout:</b>"
    else:
        title = f"<b>Current workout</b> · {format_duration(elapsed_minutes)}"
    lines = [f"{title}\n"]
    for ex in exercises:
        lines.append(f"<b>{escape(ex['exercise_name'])}</b>")
        # у черновиков, начатых до заметок к упражнениям, ключа нет
        if ex.get("notes"):
            lines.append(f"<i>{escape(ex['notes'])}</i>")
        lines.extend(format_set_lines(sets_from_fsm(ex["sets"])))
        lines.append("")
    return "\n".join(lines)


def format_sets_prompt(exercise_name: str | None = None) -> str:
    prompt = (
        "Enter set (e.g. <code>100x5</code>, <code>BWx10</code>"
        " or time <code>BWx1:30</code> / <code>BWx90s</code>)"
        " or any text to add a note:"
    )
    if exercise_name is None:
        return prompt
    return f"<b>{escape(exercise_name)}</b>\n\n{prompt}"


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
