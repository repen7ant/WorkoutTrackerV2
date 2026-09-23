from bot.catalog.models import Exercise


def format_exercise_list(exercises: list[Exercise], offset: int = 0) -> str:
    """Упражнения должны быть загружены вместе с muscles."""
    if not exercises:
        return "No exercises found."

    lines = ["<b>Exercises:</b>\n"]
    for i, exercise in enumerate(exercises, start=1 + offset):
        muscles = exercise.muscles
        muscle_str = " · ".join(m.name for m in muscles) if muscles else "—"
        lines.append(f"{i}. {exercise.name}")
        lines.append(f"   {muscle_str}\n")

    return "\n".join(lines)
