"""
Правила программы тренировок.

Цифры подходов проверяет SetEntry — те же правила, что у записи тренировки.
Остальные пределы держат кнопки и сообщения Telegram в разумном размере.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from bot.workouts.domain import MAX_EXERCISE_NOTES, SetEntry

MAX_WEEKS = 12
MAX_DAYS = 10
MAX_DAY_EXERCISES = 12
MAX_EXERCISE_SETS = 10
# колонки program_days.name и program_exercises.exercise_name
MAX_DAY_NAME = 32
MAX_EXERCISE_NAME = 128


class InvalidProgram(ValueError):
    pass


def week_count(n: int) -> str:
    return f"{n} week" if n == 1 else f"{n} weeks"


@dataclass(frozen=True)
class PlanExercise:
    name: str
    # подходы на каждую неделю; пусто — на этой неделе упражнения нет
    weeks: tuple[tuple[SetEntry, ...], ...]
    notes: str | None  # подсказка ИИ, в лог не пишется

    @classmethod
    def create(
        cls, name: str, weeks: list[list[SetEntry]], notes: str | None = None
    ) -> "PlanExercise":
        name = name.strip()
        if not name:
            raise InvalidProgram("exercise name is empty")
        if len(name) > MAX_EXERCISE_NAME:
            raise InvalidProgram(
                f"exercise name is too long (max {MAX_EXERCISE_NAME} characters)"
            )
        if len(weeks) > MAX_WEEKS:
            raise InvalidProgram(f"too many weeks (max {MAX_WEEKS})")
        for n, sets in enumerate(weeks, start=1):
            if len(sets) > MAX_EXERCISE_SETS:
                raise InvalidProgram(
                    f"too many sets in week {n} (max {MAX_EXERCISE_SETS})"
                )
        if not any(weeks):
            raise InvalidProgram("exercise has no sets in any week")
        notes = notes.strip() if notes else None
        if notes and len(notes) > MAX_EXERCISE_NOTES:
            raise InvalidProgram(
                f"notes are too long (max {MAX_EXERCISE_NOTES} characters)"
            )
        return cls(
            name=name,
            weeks=tuple(tuple(sets) for sets in weeks),
            notes=notes or None,
        )


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
    """
    Дни × недели. Позиция дня — его место в программе, с 1; у всех
    упражнений одно число недель — длина программы.
    """

    days: tuple[PlanDay, ...]
    weeks: int

    @classmethod
    def create(cls, days: list[PlanDay]) -> "ProgramPlan":
        if not days:
            raise InvalidProgram("program has no days")
        if len(days) > MAX_DAYS:
            raise InvalidProgram(f"too many days (max {MAX_DAYS})")
        weeks = len(days[0].exercises[0].weeks)
        for day in days:
            for ex in day.exercises:
                if len(ex.weeks) != weeks:
                    raise InvalidProgram(different_weeks(ex.name, len(ex.weeks), weeks))
        seen: set[str] = set()
        for day in days:
            # имена дней — кнопки выбора дня
            key = day.name.casefold()
            if key in seen:
                raise InvalidProgram(f'duplicate day "{day.name}"')
            seen.add(key)
        return cls(days=tuple(days), weeks=weeks)


def different_weeks(name: str, has: int, program: int) -> str:
    return f'"{name}" has {week_count(has)}, the program has {program}'


def sessions(days: Sequence, weeks: int) -> list[tuple[int, int]]:
    """
    Сессии программы по порядку: (неделя, позиция дня). День без единого
    подхода на этой неделе — не сессия. days — PlanDay или StoredDay:
    нужны exercises с weeks.
    """
    return [
        (week, position)
        for week in range(1, weeks + 1)
        for position, day in enumerate(days, start=1)
        if any(ex.weeks[week - 1] for ex in day.exercises)
    ]
