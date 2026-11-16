from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.catalog.api import ExerciseInfo

# все кнопки мастера импорта начинаются с него: устаревшие ловит один обработчик
IMPORT_PREFIX = "pi_"


class ImportPick(CallbackData, prefix="pi_pick"):
    exercise_id: int
    # сколько названий осталось сопоставить: второй тап по той же кнопке
    # иначе сопоставил бы это упражнение следующему названию
    left: int


def match_kb(similar: list[ExerciseInfo], left: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ex in similar:
        builder.button(
            text=ex.name, callback_data=ImportPick(exercise_id=ex.id, left=left)
        )
    builder.button(text="Create new", callback_data="pi_create")
    builder.button(text="Cancel import", callback_data="pi_cancel")
    builder.adjust(1)
    return builder.as_markup()


def muscles_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Back", callback_data="pi_back")
    builder.button(text="Cancel import", callback_data="pi_cancel")
    builder.adjust(1)
    return builder.as_markup()


def confirm_kb(replacing: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Replace current program" if replacing else "Save program",
        callback_data="pi_save",
    )
    builder.button(text="Cancel import", callback_data="pi_cancel")
    builder.adjust(1)
    return builder.as_markup()
