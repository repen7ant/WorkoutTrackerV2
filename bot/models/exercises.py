from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class Exercise(Base):
    """
    Упражнение (пользовательское или из базы по умолчанию)
    """

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
