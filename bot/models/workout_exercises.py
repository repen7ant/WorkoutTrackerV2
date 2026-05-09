from sqlalchemy import ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class WorkoutExercises(Base):
    """
    Упражнение в рамках конкретной тренировки
    """

    __tablename__ = "workouts_exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
