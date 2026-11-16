from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class ExportPeriod(CallbackData, prefix="exp_period"):
    period: str


def export_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Last month", callback_data=ExportPeriod(period="month").pack())
    builder.button(
        text="Last 6 months", callback_data=ExportPeriod(period="6months").pack()
    )
    builder.button(text="Last year", callback_data=ExportPeriod(period="year").pack())
    builder.button(text="All time", callback_data=ExportPeriod(period="all").pack())
    builder.button(text="Cancel", callback_data="exp_cancel")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def wishes_kb(has_previous: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_previous:
        builder.button(text="Keep previous", callback_data="exp_wishes_keep")
    builder.button(text="Skip", callback_data="exp_wishes_skip")
    builder.button(text="Cancel", callback_data="exp_cancel")
    builder.adjust(1)
    return builder.as_markup()
