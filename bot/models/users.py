from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class User(Base):
    """
    Пользователь бота (Telegram аккаунт)
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
