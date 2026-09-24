from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class Workout(Base):
    """
    Тренировка пользователя в конкретный день
    """

    __tablename__ = "workouts"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class WorkoutExercise(Base):
    """
    Упражнение в рамках конкретной тренировки

    Название копируется сюда при сохранении: упражнение могут удалить из
    каталога, а тренировка должна остаться такой, какой была. Тогда
    exercise_id становится NULL, а exercise_name остаётся.
    """

    __tablename__ = "workout_exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id"))
    exercise_id: Mapped[int | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL")
    )
    exercise_name: Mapped[str] = mapped_column(String(128))


class Set(Base):
    """
    Вес и количество повторений
    """

    __tablename__ = "sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    workout_exercise_id: Mapped[int] = mapped_column(ForeignKey("workout_exercises.id"))
    reps: Mapped[int] = mapped_column(SmallInteger)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
