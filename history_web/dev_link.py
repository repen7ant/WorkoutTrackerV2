"""
Ссылка для открытия Mini App в обычном браузере.

telegram-web-app.js берёт initData из #tgWebAppData, поэтому страница
проходит ту же проверку подписи, что и внутри Telegram.

uv run -m history_web.dev_link <user_id>
"""

import sys
from datetime import UTC, datetime
from urllib.parse import quote

from bot.config import Settings
from history_web.auth import sign_init_data


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("usage: uv run -m history_web.dev_link <user_id>")
    token = Settings().bot.token.get_secret_value()
    init_data = sign_init_data(token, int(sys.argv[1]), datetime.now(UTC))
    print(
        f"http://localhost:8080/#tgWebAppData={quote(init_data, safe='')}"
        "&tgWebAppVersion=8.0&tgWebAppPlatform=web"
    )


main()
