from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class Muscle(Base):
    """
    Группа мышц
    """

    __tablename__ = "muscles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
