from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def yes_no_kb(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Yes", callback_data=yes_data)
    builder.button(text="No", callback_data=no_data)
    # в один ряд: случайное второе нажатие Finish session попадёт в No, а не в Yes
    builder.adjust(2)
    return builder.as_markup()
