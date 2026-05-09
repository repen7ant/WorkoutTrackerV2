from bot.models.exercises import Exercise
from bot.models.muscles import Muscle
from bot.models.workouts import Workout


def format_exercise_list(
    exercises: list[tuple[Exercise, list[Muscle]]], offset: int = 0
) -> str:
    if not exercises:
        return "No exercises found."

    lines = ["<b>Exercises:</b>\n"]
    for i, (exercise, muscles) in enumerate(exercises, start=1 + offset):
        muscle_str = " · ".join(m.name for m in muscles) if muscles else "—"
        lines.append(f"{i}. {exercise.name}")
        lines.append(f"   {muscle_str}\n")

    return "\n".join(lines)


def format_exercise_log(
    exercise_name: str,
    sessions: list[
        dict
    ],  # [{"date": date, "notes": str|None, "sets": [{"weight": Decimal|None, "reps": int}]}]
) -> str:
    if not sessions:
        return f"<b>{exercise_name}</b>\n\nNo history yet."

    lines = [f"<b>{exercise_name}</b>\n"]
    for session in sessions:
        date_str = session["date"].strftime("%d-%m-%y")
        lines.append(f"<b>{date_str}</b>")
        if session["notes"]:
            lines.append(f"<i>{session['notes']}</i>")
        for i, s in enumerate(session["sets"], start=1):
            weight = "BW" if s["weight"] is None else f"{s['weight']}kg"
            lines.append(f"  {i}. {weight} x {s['reps']}")
        lines.append("")

    return "\n".join(lines)


def format_workout_summary(
    exercises: list[dict],  # данные из FSM перед сохранением
    exercise_names: dict[int, str],  # {exercise_id: name}
) -> str:
    if not exercises:
        return "No exercises recorded."

    lines = ["<b>Workout summary:</b>\n"]
    for ex in exercises:
        name = exercise_names.get(ex["exercise_id"], "Unknown")
        lines.append(f"<b>{name}</b>")
        for i, s in enumerate(ex["sets"], start=1):
            weight = "BW" if s["weight"] is None else f"{s['weight']}kg"
            lines.append(f"  {i}. {weight} x {s['reps']}")
        lines.append("")

    return "\n".join(lines)


def format_workout_list(workouts: list[Workout]) -> str:
    if not workouts:
        return "No workouts yet."
    lines = ["<b>Workout history:</b>\n"]
    for w in workouts:
        date_str = w.date.strftime("%d-%m-%y")
        notes_str = f" — {w.notes}" if w.notes else ""
        lines.append(f"{date_str}{notes_str}")
    return "\n".join(lines)


def format_workout_detail(workout: Workout, exercises: list[dict]) -> str:
    date_str = workout.date.strftime("%d-%m-%y")
    lines = [f"<b>{date_str}</b>"]
    if workout.notes:
        lines.append(f"<i>{workout.notes}</i>")
    lines.append("")
    for ex in exercises:
        lines.append(f"<b>{ex['exercise_name']}</b>")
        for i, s in enumerate(ex["sets"], start=1):
            weight = "BW" if s["weight"] is None else f"{s['weight']}kg"
            lines.append(f"  {i}. {weight} x {s['reps']}")
        lines.append("")
    return "\n".join(lines)
