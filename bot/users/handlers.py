from contextlib import suppress
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.users.keyboards import SettingsChange, settings_kb, timezone_kb
from bot.users.models import User
from bot.users.service import update_setting
from bot.users.settings import Setting, local_now

router = Router(name="settings")

SETTINGS_TEXT = (
    "<b>Settings</b>\n\n"
    "Workout date — ask or always today.\n"
    "Workout notes — ask or skip.\n"
    "Exercise log — past workouts shown when you pick an exercise.\n"
    "Time zone — sets today's date and workout times."
)


@router.message(Command("settings"))
async def cmd_settings(message: Message, db_user: User) -> None:
    await message.answer(
        SETTINGS_TEXT, parse_mode="HTML", reply_markup=settings_kb(db_user)
    )


@router.callback_query(SettingsChange.filter())
async def cb_settings_change(
    call: CallbackQuery,
    callback_data: SettingsChange,
    session: AsyncSession,
    db_user: User,
) -> None:
    await update_setting(session, db_user, callback_data.setting, callback_data.value)
    # текст тоже: после выбора пояса в сообщении был вопрос о времени.
    # То же значение — Telegram отвечает «message is not modified»
    with suppress(TelegramBadRequest):
        await call.message.edit_text(
            SETTINGS_TEXT, parse_mode="HTML", reply_markup=settings_kb(db_user)
        )
    if callback_data.setting == Setting.TIMEZONE:
        await call.answer(f"Saved. Your time: {local_now(db_user.utc_offset):%H:%M}")
    else:
        await call.answer()


@router.callback_query(F.data == "settings_tz")
async def cb_timezone_menu(call: CallbackQuery) -> None:
    with suppress(TelegramBadRequest):
        await call.message.edit_text(
            "What time is it for you now?", reply_markup=timezone_kb(datetime.now(UTC))
        )
    await call.answer()


@router.callback_query(F.data == "settings_back")
async def cb_settings_back(call: CallbackQuery, db_user: User) -> None:
    with suppress(TelegramBadRequest):
        await call.message.edit_text(
            SETTINGS_TEXT, parse_mode="HTML", reply_markup=settings_kb(db_user)
        )
    await call.answer()
