"""
Кто открыл Mini App.

Telegram подписывает initData токеном бота, поэтому id пользователя из неё
можно брать без отдельного входа — если подпись сошлась.
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

from aiogram.utils.web_app import safe_parse_webapp_init_data

# подпись не истекает сама, а страница может висеть открытой сколько угодно
MAX_AGE = timedelta(hours=24)


class Unauthorized(Exception):
    pass


def user_id_from_init_data(token: str, init_data: str, now: datetime) -> int:
    try:
        data = safe_parse_webapp_init_data(token, init_data)
    except ValueError as e:
        raise Unauthorized from e
    if data.user is None or now - data.auth_date > MAX_AGE:
        raise Unauthorized
    return data.user.id


def sign_init_data(token: str, user_id: int, auth_date: datetime) -> str:
    """initData так, как её подписал бы Telegram, — для тестов и dev_link."""
    fields = {
        "auth_date": str(int(auth_date.timestamp())),
        "user": json.dumps({"id": user_id, "first_name": "Dev"}),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(
        secret, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(fields)
