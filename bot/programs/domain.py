"""
Правила программы тренировок.

Цифры подходов проверяет SetEntry — те же правила, что у записи тренировки.
Остальные пределы держат кнопки и сообщения Telegram в разумном размере.
"""

from dataclasses import dataclass

from bot.workouts.domain import MAX_EXERCISE_NOTES, SetEntry

MAX_DAYS = 10
MAX_DAY_EXERCISES = 12
MAX_EXERCISE_SETS = 10
# колонки program_days.name и program_exercises.exercise_name
MAX_DAY_NAME = 32
MAX_EXERCISE_NAME = 128


class InvalidProgram(ValueError):
    pass


@dataclass(frozen=True)
class PlanExercise:
    name: str
    sets: tuple[SetEntry, ...]
    notes: str | None  # подсказка ИИ, в лог не пишется

    @classmethod
    def create(
        cls, name: str, sets: list[SetEntry], notes: str | None = None
    ) -> "PlanExercise":
        name = name.strip()
        if not name:
            raise InvalidProgram("exercise name is empty")
        if len(name) > MAX_EXERCISE_NAME:
            raise InvalidProgram(
                f"exercise name is too long (max {MAX_EXERCISE_NAME} characters)"
            )
        if not sets:
            raise InvalidProgram("exercise has no sets")
        if len(sets) > MAX_EXERCISE_SETS:
            raise InvalidProgram(f"too many sets (max {MAX_EXERCISE_SETS})")
        notes = notes.strip() if notes else None
        if notes and len(notes) > MAX_EXERCISE_NOTES:
            raise InvalidProgram(
                f"notes are too long (max {MAX_EXERCISE_NOTES} characters)"
            )
        return cls(name=name, sets=tuple(sets), notes=notes or None)


@dataclass(frozen=True)
class PlanDay:
    name: str
    exercises: tuple[PlanExercise, ...]

    @classmethod
    def create(cls, name: str, exercises: list[PlanExercise]) -> "PlanDay":
        name = name.strip()
        if not name:
            raise InvalidProgram("day name is empty")
        if len(name) > MAX_DAY_NAME:
            raise InvalidProgram(
                f"day name is too long (max {MAX_DAY_NAME} characters)"
            )
        if not exercises:
            raise InvalidProgram(f'day "{name}" has no exercises')
        if len(exercises) > MAX_DAY_EXERCISES:
            raise InvalidProgram(
                f'day "{name}" has too many exercises (max {MAX_DAY_EXERCISES})'
            )
        return cls(name=name, exercises=tuple(exercises))


@dataclass(frozen=True)
class ProgramPlan:
    """Дни идут ротацией в этом порядке; позиция дня — его место, с 1."""

    days: tuple[PlanDay, ...]

    @classmethod
    def create(cls, days: list[PlanDay]) -> "ProgramPlan":
        if not days:
            raise InvalidProgram("program has no days")
        if len(days) > MAX_DAYS:
            raise InvalidProgram(f"too many days (max {MAX_DAYS})")
        seen: set[str] = set()
        for day in days:
            # имена дней — кнопки выбора дня
            key = day.name.casefold()
            if key in seen:
                raise InvalidProgram(f'duplicate day "{day.name}"')
            seen.add(key)
        return cls(days=tuple(days))


def next_after(position: int, day_count: int) -> int:
    """Позиция дня после position, по кругу."""
    return position % day_count + 1
