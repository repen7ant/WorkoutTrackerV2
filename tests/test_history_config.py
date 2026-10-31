import pytest

from bot.config import HistoryConfig

URL = "https://history.example.com"


@pytest.mark.parametrize(
    ("config", "user_id", "expected"),
    [
        (HistoryConfig(), 1, False),
        (HistoryConfig(mode="miniapp"), 1, False),
        (HistoryConfig(mode="miniapp", webapp_url=URL), 1, True),
        (HistoryConfig(webapp_url=URL, beta_user_ids=[1]), 1, True),
        (HistoryConfig(webapp_url=URL, beta_user_ids=[1]), 2, False),
    ],
)
def test_uses_miniapp(config, user_id, expected):
    assert config.uses_miniapp(user_id) is expected
