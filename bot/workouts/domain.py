"""
Правила записи тренировки.

Любой способ ввода — чат, будущий импорт, что угодно — собирает тренировку
через эти конструкторы, поэтому получить недопустимые данные в обход правил
нельзя.
"""

from dataclasses import dataclass
from datetime import date, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Границы берутся из схемы (models.Set): вес — Numeric(5, 2), повторения и
# секунды — SmallInteger. Всё, что не влезает, раньше доходило до INSERT и
# роняло сохранение уже собранной тренировки.
MAX_WEIGHT = Decimal("999.99")
WEIGHT_STEP = Decimal("0.01")
MAX_REPS = 32767
MAX_SECONDS = 32767
# заметки упражнения идут в лог из 10 тренировок, а сообщение Telegram —
# не длиннее 4096 символов
MAX_EXERCISE_NOTES = 200
# дольше — скорее всего, тренировку забыли закончить или ошиблись в правке
MAX_WORKOUT_DURATION = timedelta(hours=6)


class InvalidWorkout(ValueError):
    pass


@dataclass(frozen=True)
class SetEntry:
    weight: Decimal | None  # None — с собственным весом
    reps: int | None = None
    seconds: int | None = None  # подход на время — вместо повторений

    @classmethod
    def create(
        cls,
        weight: Decimal | None,
        reps: int | None = None,
        seconds: int | None = None,
    ) -> "SetEntry":
        if (reps is None) == (seconds is None):
            raise InvalidWorkout("set must have either reps or seconds")
        if reps is not None and not 0 < reps <= MAX_REPS:
            raise InvalidWorkout(f"reps must be 1..{MAX_REPS}")
        if seconds is not None and not 0 < seconds <= MAX_SECONDS:
            raise InvalidWorkout(f"seconds must be 1..{MAX_SECONDS}")
        if weight is not None:
            # NaN и Infinity парсятся молча, а сравнения с NaN всегда ложны —
            # поэтому конечность проверяем первой
            if not weight.is_finite() or weight < 0:
                raise InvalidWorkout("weight must be a non-negative number")
            # округляем до масштаба колонки здесь, иначе Postgres округлит сам
            # и в истории окажется не то число, что бот показал при вводе
            try:
                weight = weight.quantize(WEIGHT_STEP, rounding=ROUND_HALF_UP)
            except InvalidOperation as e:
                # слишком длинное число: два знака после запятой не влезают
                # в точность Decimal
                raise InvalidWorkout(f"weight must be at most {MAX_WEIGHT}") from e
            if weight > MAX_WEIGHT:
                raise InvalidWorkout(f"weight must be at most {MAX_WEIGHT}")
        return cls(weight=weight, reps=reps, seconds=seconds)


def exercise_notes(text: str | None) -> str | None:
    """Заметка к упражнению: без пробелов по краям, пустая — None."""
    text = text.strip() if text else None
    if text and len(text) > MAX_EXERCISE_NOTES:
        raise InvalidWorkout(
            f"exercise notes must be at most {MAX_EXERCISE_NOTES} characters"
        )
    return text or None


@dataclass(frozen=True)
class ExerciseEntry:
    exercise_id: int | None  # None — упражнение удалено из каталога
    sets: tuple[SetEntry, ...]
    name: str | None = None  # только у удалённого: каталог его уже не знает
    notes: str | None = None

    @classmethod
    def create(
        cls, exercise_id: int, sets: list[SetEntry], notes: str | None = None
    ) -> "ExerciseEntry":
        if not sets:
            raise InvalidWorkout("exercise must have at least one set")
        return cls(
            exercise_id=exercise_id, sets=tuple(sets), notes=exercise_notes(notes)
        )

    @classmethod
    def deleted(
        cls, name: str, sets: list[SetEntry], notes: str | None = None
    ) -> "ExerciseEntry":
        """Удалённое из каталога упражнение, которое осталось в тренировке
        при её правке."""
        name = name.strip()
        if not name:
            raise InvalidWorkout("deleted exercise must have a name")
        if not sets:
            raise InvalidWorkout("exercise must have at least one set")
        return cls(
            exercise_id=None, sets=tuple(sets), name=name, notes=exercise_notes(notes)
        )


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
    # по часам пользователя; оба или ни одного
    start_time: time | None = None
    end_time: time | None = None

    @classmethod
    def create(
        cls,
        user_id: int,
        workout_date: date,
        notes: str | None,
        exercises: list[ExerciseEntry],
        start_time: time | None = None,
        end_time: time | None = None,
    ) -> "WorkoutRecord":
        if not exercises:
            raise InvalidWorkout("workout must have at least one exercise")
        if (start_time is None) != (end_time is None):
            raise InvalidWorkout("start and end time must be set together")
        if start_time is not None and end_time is not None:
            duration = timedelta(minutes=duration_minutes(start_time, end_time))
            if duration > MAX_WORKOUT_DURATION:
                raise InvalidWorkout("workout can't be longer than 6 hours")
        notes = notes.strip() if notes else None
        return cls(
            user_id=user_id,
            date=workout_date,
            notes=notes or None,
            exercises=tuple(exercises),
            start_time=start_time,
            end_time=end_time,
        )

    def positioned(self) -> list[tuple[int, ExerciseEntry]]:
        return list(enumerate(self.exercises, start=1))


# То, что читается из журнала обратно: уже сохранённое, поэтому без проверок.


@dataclass(frozen=True)
class LoggedExercise:
    exercise_id: int | None  # None — упражнение удалено из каталога
    name: str  # название на момент тренировки
    sets: list[SetEntry]
    notes: str | None = None


@dataclass(frozen=True)
class LoggedWorkout:
    id: int
    date: date
    notes: str | None
    exercises: list[LoggedExercise]
    start_time: time | None = None
    end_time: time | None = None


def duration_minutes(start: time, end: time) -> int:
    """Через полночь тоже: 23:30–00:45 — 75 минут."""
    minutes = (end.hour - start.hour) * 60 + end.minute - start.minute
    return minutes % (24 * 60)
