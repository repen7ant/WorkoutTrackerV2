from sqlalchemy import BigInteger, ColumnElement, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base


class SharedOrOwn:
    """
    Запись каталога: user_id IS NULL — общая, иначе — личная запись пользователя.
    """

    @classmethod
    def visible_to(cls, user_id: int) -> ColumnElement[bool]:
        return cls.user_id.is_(None) | (cls.user_id == user_id)  # type: ignore[attr-defined]

    @classmethod
    def owned_by(cls, user_id: int) -> ColumnElement[bool]:
        return cls.user_id == user_id  # type: ignore[attr-defined]


class Exercise(SharedOrOwn, Base):
    """
    Упражнение (пользовательское или из базы по умолчанию)
    """

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    muscles: Mapped[list["Muscle"]] = relationship(
        secondary="exercise_muscles",
        lazy="noload",
    )


class Muscle(SharedOrOwn, Base):
    """
    Группа мышц
    """

    __tablename__ = "muscles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))


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
