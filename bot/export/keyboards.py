from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class ExportPeriod(CallbackData, prefix="exp_period"):
    period: str


def export_period_kb(has_program: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_program:
        builder.button(
            text="Current program", callback_data=ExportPeriod(period="program")
        )
    builder.button(text="Last month", callback_data=ExportPeriod(period="month"))
    builder.button(text="Last 3 months", callback_data=ExportPeriod(period="3months"))
    builder.button(text="Last 6 months", callback_data=ExportPeriod(period="6months"))
    builder.button(text="All time", callback_data=ExportPeriod(period="all"))
    builder.button(text="Cancel", callback_data="exp_cancel")
    builder.adjust(*[1] * has_program, 2, 2, 1)
    return builder.as_markup()


def wishes_kb(has_previous: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_previous:
        builder.button(text="Keep previous", callback_data="exp_wishes_keep")
    builder.button(text="Skip", callback_data="exp_wishes_skip")
    builder.button(text="Cancel", callback_data="exp_cancel")
    builder.adjust(1)
    return builder.as_markup()
