from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class Set(Base):
    """
    Вес и количество повторений
    """

    __tablename__ = "sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    workout_exercise_id: Mapped[int] = mapped_column(ForeignKey("workout_exercises.id"))
    reps: Mapped[int] = mapped_column(SmallInteger)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
