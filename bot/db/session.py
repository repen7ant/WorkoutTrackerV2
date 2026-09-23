from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Модели разложены по модулям и ссылаются друг на друга по имени таблицы
# (exercises.user_id -> users.id). Чтобы такие ссылки разрешались, в метадате
# должны быть все таблицы, даже если процессу, как сиду, нужна часть из них.
import bot.models  # noqa: F401
from bot.config import Settings

settings = Settings()
engine = create_async_engine(settings.db.url)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
