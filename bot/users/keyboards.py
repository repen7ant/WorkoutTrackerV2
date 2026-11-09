from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.users.models import User
from bot.users.settings import Setting, next_log_size


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
    builder.adjust(1)
    return builder.as_markup()
