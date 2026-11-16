from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class Program(Base):
    """
    Программа тренировок пользователя — одна активная, без срока
    """

    __tablename__ = "programs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), unique=True
    )
    # позиция дня, который бот предложит следующим
    next_position: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1"
    )


class ProgramDay(Base):
    __tablename__ = "program_days"
    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str] = mapped_column(String(32))


class ProgramExercise(Base):
    """
    Упражнение дня программы. Название копируется, как в workout_exercises:
    упражнение могут удалить из каталога.
    """

    __tablename__ = "program_exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    day_id: Mapped[int] = mapped_column(
        ForeignKey("program_days.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    exercise_id: Mapped[int | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"), index=True
    )
    exercise_name: Mapped[str] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)


class ProgramSet(Base):
    __tablename__ = "program_sets"
    __table_args__ = (
        CheckConstraint(
            "(reps IS NULL) <> (seconds IS NULL)",
            name="program_sets_reps_or_seconds_check",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    program_exercise_id: Mapped[int] = mapped_column(
        ForeignKey("program_exercises.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reps: Mapped[int | None] = mapped_column(SmallInteger)
    seconds: Mapped[int | None] = mapped_column(SmallInteger)
