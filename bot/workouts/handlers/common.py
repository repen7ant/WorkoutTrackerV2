from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.workouts.formatters import format_workout_main
from bot.workouts.keyboards import workout_main_kb

# Эти команды обязаны работать и посреди ввода: иначе /history во время
# заметок молча становится текстом заметки, а /start — подходом.
BOT_COMMANDS = Command("start", "workout", "exercises", "history", "export")


async def send_workout_main(target: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text = format_workout_main(data.get("exercises", []))

    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=workout_main_kb())
    else:
        await target.message.edit_text(
            text, parse_mode="HTML", reply_markup=workout_main_kb()
        )


async def remove_kb(call: CallbackQuery) -> None:
    await call.message.edit_reply_markup(reply_markup=None)
