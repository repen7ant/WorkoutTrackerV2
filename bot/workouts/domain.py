"""
Правила записи тренировки.

Любой способ ввода — чат, будущий импорт, что угодно — собирает тренировку
через эти конструкторы, поэтому получить недопустимые данные в обход правил
нельзя.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

# Границы берутся из схемы (models.Set): вес — Numeric(5, 2), повторения —
# SmallInteger. Всё, что не влезает, раньше доходило до INSERT и роняло
# сохранение уже собранной тренировки.
MAX_WEIGHT = Decimal("999.99")
WEIGHT_STEP = Decimal("0.01")
MAX_REPS = 32767


class InvalidWorkout(ValueError):
    pass


@dataclass(frozen=True)
class SetEntry:
    weight: Decimal | None  # None — с собственным весом
    reps: int

    @classmethod
    def create(cls, weight: Decimal | None, reps: int) -> "SetEntry":
        if not 0 < reps <= MAX_REPS:
            raise InvalidWorkout(f"reps must be 1..{MAX_REPS}")
        if weight is not None:
            # NaN и Infinity парсятся молча, а сравнения с NaN всегда ложны —
            # поэтому конечность проверяем первой
            if not weight.is_finite() or weight < 0:
                raise InvalidWorkout("weight must be a non-negative number")
            # округляем до масштаба колонки здесь, иначе Postgres округлит сам
            # и в истории окажется не то число, что бот показал при вводе
            weight = weight.quantize(WEIGHT_STEP, rounding=ROUND_HALF_UP)
            if weight > MAX_WEIGHT:
                raise InvalidWorkout(f"weight must be at most {MAX_WEIGHT}")
        return cls(weight=weight, reps=reps)


@dataclass(frozen=True)
class ExerciseEntry:
    exercise_id: int
    sets: tuple[SetEntry, ...]

    @classmethod
    def create(cls, exercise_id: int, sets: list[SetEntry]) -> "ExerciseEntry":
        if not sets:
            raise InvalidWorkout("exercise must have at least one set")
        return cls(exercise_id=exercise_id, sets=tuple(sets))


@dataclass(frozen=True)
class WorkoutRecord:
    """
    Тренировка, готовая к сохранению.

    Упражнения идут в порядке выполнения: позиция упражнения — это его место
    в exercises, а подходы — в порядке ввода.
    """

    user_id: int
    date: date
    notes: str | None
    exercises: tuple[ExerciseEntry, ...]

    @classmethod
    def create(
        cls,
        user_id: int,
        workout_date: date,
        notes: str | None,
        exercises: list[ExerciseEntry],
    ) -> "WorkoutRecord":
        if not exercises:
            raise InvalidWorkout("workout must have at least one exercise")
        notes = notes.strip() if notes else None
        return cls(
            user_id=user_id,
            date=workout_date,
            notes=notes or None,
            exercises=tuple(exercises),
        )

    def positioned(self) -> list[tuple[int, ExerciseEntry]]:
        return list(enumerate(self.exercises, start=1))


# То, что читается из журнала обратно: уже сохранённое, поэтому без проверок.


@dataclass(frozen=True)
class LoggedExercise:
    exercise_id: int
    sets: list[SetEntry]


@dataclass(frozen=True)
class LoggedWorkout:
    id: int
    date: date
    notes: str | None
    exercises: list[LoggedExercise]
