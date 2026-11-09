from sqlalchemy import BigInteger, SmallInteger, String, true
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class User(Base):
    """
    Пользователь бота (Telegram аккаунт) и его настройки из /settings
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    ask_workout_date: Mapped[bool] = mapped_column(default=True, server_default=true())
    ask_workout_notes: Mapped[bool] = mapped_column(default=True, server_default=true())
    exercise_log_size: Mapped[int] = mapped_column(
        SmallInteger, default=10, server_default="10"
    )
    # часовой пояс — минуты от UTC; 180 — Москва
    utc_offset: Mapped[int] = mapped_column(
        SmallInteger, default=180, server_default="180"
    )
