import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class LogRenderer(StrEnum):
    JSON = "json"
    CONSOLE = "console"


class BotConfig(BaseModel):
    token: SecretStr


class DatabaseConfig(BaseModel):
    url: str


class RedisConfig(BaseModel):
    # Хранилище FSM. Дефолт рассчитан на docker-compose, где бот и redis
    # в одной сети; локально бот ходит через host-сеть, поэтому там нужен
    # localhost — см. settings.example.toml.
    url: str = "redis://redis:6379/0"


class LogConfig(BaseModel):
    project_name: str
    show_datetime: bool
    datetime_format: str
    show_debug_logs: bool
    time_in_utc: bool
    use_colors_in_console: bool
    renderer: LogRenderer
    allow_third_party_logs: bool


class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    """
    Источник для чтения настроек из TOML-файла.
    """

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        file_path = Path(__file__).resolve().parent.parent.joinpath("settings.toml")
        if not file_path.exists():
            return {}
        with file_path.open("rb") as f:
            return tomllib.load(f)


class Settings(BaseSettings):
    # Перечисляем, какие ключи ожидаются в конфиге
    bot: BotConfig
    logs: LogConfig
    db: DatabaseConfig
    redis: RedisConfig = RedisConfig()

    """
    Задаём параметры чтения конфига:
    1. Разделитель вложенных ключей при чтении переменных окружения __
    Т.е. ключ token внутри секции bot будет ожидаться как BOT__TOKEN
    2. extra="ignore" - игнорируем любые ключи, которые не описаны в конфиге
    """
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls),
        )
