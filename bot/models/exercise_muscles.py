from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class ExerciseMuscle(Base):
    """
    Связь упражнения с задействованными мышцами
    """

    __tablename__ = "exercise_muscles"
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True
    )
    muscle_id: Mapped[int] = mapped_column(
        ForeignKey("muscles.id", ondelete="CASCADE"), primary_key=True
    )
