"""
Кнопка меню чата — слева от поля ввода.

У кого включён Mini App, она открывает его, у остальных — обычный список
команд. Ставится при старте бота по тем же настройкам [history], что и ответ
/history, поэтому откат режима убирает и кнопку.
"""

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    MenuButtonCommands,
    MenuButtonDefault,
    MenuButtonUnion,
    MenuButtonWebApp,
    WebAppInfo,
)
from structlog.typing import FilteringBoundLogger

from bot.config import HistoryConfig, HistoryMode

logger: FilteringBoundLogger = structlog.get_logger()


def menu_buttons(
    config: HistoryConfig,
) -> tuple[MenuButtonUnion, dict[int, MenuButtonUnion]]:
    """Кнопка по умолчанию и личные кнопки по id пользователя."""
    if config.webapp_url is None:
        return MenuButtonCommands(), {}
    app = MenuButtonWebApp(text="History", web_app=WebAppInfo(url=config.webapp_url))
    if config.mode == HistoryMode.MINIAPP:
        # личная кнопка беты больше не нужна: её заменяет общая
        return app, dict.fromkeys(config.beta_user_ids, MenuButtonDefault())
    return MenuButtonCommands(), dict.fromkeys(config.beta_user_ids, app)


async def setup_menu_button(bot: Bot, config: HistoryConfig) -> None:
    default, personal = menu_buttons(config)
    # без кнопки бот работает как раньше, поэтому ошибка не мешает запуску
    try:
        await bot.set_chat_menu_button(menu_button=default)
    except TelegramAPIError as e:
        await logger.awarning("Menu button not set", error=str(e))
    for user_id, button in personal.items():
        try:
            await bot.set_chat_menu_button(chat_id=user_id, menu_button=button)
        except TelegramAPIError as e:
            # например, пользователь ещё ни разу не писал боту
            await logger.awarning("Menu button not set", user_id=user_id, error=str(e))
