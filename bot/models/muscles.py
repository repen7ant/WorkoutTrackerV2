from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class Muscle(Base):
    """
    Группа мышц
    """

    __tablename__ = "muscles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
