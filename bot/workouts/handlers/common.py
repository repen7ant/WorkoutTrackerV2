from datetime import UTC, datetime
from typing import Any

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.workouts.draft import minutes_since_start, plan_statuses, plan_todo
from bot.workouts.formatters import format_workout_main
from bot.workouts.keyboards import workout_main_kb

# Эти команды обязаны работать и посреди ввода: иначе /history во время
# заметок молча становится текстом заметки, а /start — подходом.
BOT_COMMANDS = Command("start", "workout", "exercises", "history", "export", "program")

LAST_WEEK = "Last week of the program — /export after it."
PROGRAM_FINISHED = "Program finished — /export your log to get the next one."


def workout_main_view(data: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    """Окно тренировки; у тренировки по программе — с планом дня."""
    elapsed = minutes_since_start(data, datetime.now(UTC))
    text = format_workout_main(
        data.get("exercises", []),
        elapsed,
        data.get("program_day"),
        plan_statuses(data),
    )
    return text, workout_main_kb(plan_todo(data))


async def send_workout_main(target: Message | CallbackQuery, state: FSMContext) -> None:
    text, kb = workout_main_view(await state.get_data())
    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


async def remove_kb(call: CallbackQuery) -> None:
    await call.message.edit_reply_markup(reply_markup=None)
