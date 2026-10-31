import asyncio

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SetChatMenuButton
from aiogram.types import (
    MenuButtonCommands,
    MenuButtonDefault,
    MenuButtonWebApp,
    WebAppInfo,
)

from bot.config import HistoryConfig
from bot.history.menu import menu_buttons, setup_menu_button

URL = "https://history.example.com"
APP = MenuButtonWebApp(text="History", web_app=WebAppInfo(url=URL))


def test_no_url_keeps_commands():
    config = HistoryConfig(mode="miniapp", beta_user_ids=[1])
    assert menu_buttons(config) == (MenuButtonCommands(), {})


def test_beta_users_get_app_in_chat_mode():
    config = HistoryConfig(webapp_url=URL, beta_user_ids=[1])
    assert menu_buttons(config) == (MenuButtonCommands(), {1: APP})


def test_everyone_gets_app_in_miniapp_mode():
    config = HistoryConfig(mode="miniapp", webapp_url=URL, beta_user_ids=[1])
    assert menu_buttons(config) == (APP, {1: MenuButtonDefault()})


class ChatNotFoundBot:
    def __init__(self):
        self.calls = []

    async def set_chat_menu_button(self, chat_id=None, menu_button=None):
        self.calls.append(chat_id)
        raise TelegramBadRequest(SetChatMenuButton(), "chat not found")


def test_telegram_errors_dont_stop_bot_startup():
    bot = ChatNotFoundBot()
    config = HistoryConfig(webapp_url=URL, beta_user_ids=[1, 2])
    asyncio.run(setup_menu_button(bot, config))
    assert bot.calls == [None, 1, 2]
