import structlog
from aiohttp import web

from bot.config import Settings
from bot.db.session import AsyncSessionLocal
from bot.logging_config import get_structlog_config
from history_web.app import create_app


def main() -> None:
    settings = Settings()
    structlog.configure(**get_structlog_config(settings.logs))
    app = create_app(settings.bot.token.get_secret_value(), AsyncSessionLocal)
    # в контейнере: снаружи до сервиса доходит только Caddy
    web.run_app(app, host="0.0.0.0", port=8080)  # noqa: S104


main()
