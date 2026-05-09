from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class HistoryPage(CallbackData, prefix="hist_page"):
    page: int


class HistoryDetail(CallbackData, prefix="hist_detail"):
    workout_id: int
    page: int  # чтобы вернуться обратно


def history_list_kb(
    workouts: list, page: int, total_pages: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for w in workouts:
        date_str = w.date.strftime("%d-%m-%y")
        notes_str = f" — {w.notes}" if w.notes else ""
        builder.button(
            text=f"{date_str}{notes_str}",
            callback_data=HistoryDetail(workout_id=w.id, page=page).pack(),
        )
    builder.adjust(1)

    nav = []
    if page > 1:
        nav.append(("←", HistoryPage(page=page - 1).pack()))
    nav.append((f"{page}/{total_pages}", "hist_noop"))
    if page < total_pages:
        nav.append(("→", HistoryPage(page=page + 1).pack()))

    for text, data in nav:
        builder.button(text=text, callback_data=data)
    builder.adjust(1, len(nav))
    return builder.as_markup()


def history_detail_kb(page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="← Back", callback_data=HistoryPage(page=page).pack())
    return builder.as_markup()
