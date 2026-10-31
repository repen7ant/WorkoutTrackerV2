from datetime import UTC, datetime, timedelta

import pytest

from history_web.auth import (
    MAX_AGE,
    Unauthorized,
    sign_init_data,
    user_id_from_init_data,
)

TOKEN = "123456:TEST"
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def test_signed_init_data_gives_user_id():
    data = sign_init_data(TOKEN, 42, auth_date=NOW)
    assert user_id_from_init_data(TOKEN, data, now=NOW) == 42


def test_foreign_signature_rejected():
    data = sign_init_data("999:OTHER", 42, auth_date=NOW)
    with pytest.raises(Unauthorized):
        user_id_from_init_data(TOKEN, data, now=NOW)


def test_stale_init_data_rejected():
    data = sign_init_data(TOKEN, 42, auth_date=NOW - MAX_AGE - timedelta(seconds=1))
    with pytest.raises(Unauthorized):
        user_id_from_init_data(TOKEN, data, now=NOW)


@pytest.mark.parametrize("raw", ["", "garbage", "user=%7B%7D&hash=abc"])
def test_malformed_init_data_rejected(raw):
    with pytest.raises(Unauthorized):
        user_id_from_init_data(TOKEN, raw, now=NOW)
