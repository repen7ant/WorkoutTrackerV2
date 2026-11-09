from datetime import datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.users.models import User
from bot.users.settings import (
    UTC_OFFSETS,
    Setting,
    format_utc_offset,
    next_log_size,
    to_local,
)


class SettingsChange(CallbackData, prefix="settings"):
    # кнопка ставит конкретное значение, а не «переключить»: иначе быстрое
    # двойное нажатие вернуло бы настройку обратно
    setting: Setting
    value: int


def settings_kb(user: User) -> InlineKeyboardMarkup:
    date = "ask" if user.ask_workout_date else "today"
    notes = "ask" if user.ask_workout_notes else "off"
    size = user.exercise_log_size
    log = f"{size} workouts" if size else "off"

    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"Workout date: {date}",
        callback_data=SettingsChange(
            setting=Setting.DATE, value=int(not user.ask_workout_date)
        ).pack(),
    )
    builder.button(
        text=f"Workout notes: {notes}",
        callback_data=SettingsChange(
            setting=Setting.NOTES, value=int(not user.ask_workout_notes)
        ).pack(),
    )
    builder.button(
        text=f"Exercise log: {log}",
        callback_data=SettingsChange(
            setting=Setting.LOG, value=next_log_size(size)
        ).pack(),
    )
    builder.button(
        text=f"Time zone: {format_utc_offset(user.utc_offset)}",
        callback_data="settings_tz",
    )
    builder.adjust(1)
    return builder.as_markup()


def timezone_kb(now: datetime) -> InlineKeyboardMarkup:
    times = sorted((f"{to_local(now, offset):%H:%M}", offset) for offset in UTC_OFFSETS)
    builder = InlineKeyboardBuilder()
    for label, offset in times:
        builder.button(
            text=label,
            callback_data=SettingsChange(setting=Setting.TIMEZONE, value=offset).pack(),
        )
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="Back", callback_data="settings_back"))
    return builder.as_markup()
