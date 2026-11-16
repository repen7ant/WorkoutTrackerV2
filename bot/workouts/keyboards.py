from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.common.keyboards import yes_no_kb


class ExerciseChoice(CallbackData, prefix="wk_ex"):
    # только id: у callback_data лимит 64 байта, и название на кириллице
    # длиннее ~28 символов в него уже не влезало
    exercise_id: int


class WkDay(CallbackData, prefix="wk_day"):
    position: int


class WkPlanEx(CallbackData, prefix="wk_plan_ex"):
    index: int  # пункт плана дня в черновике


def day_choice_kb(
    days: list[tuple[int, str]], next_position: int
) -> InlineKeyboardMarkup:
    """Следующий по ротации день — первой кнопкой, остальные — по два в ряд."""
    positions = [pos for pos, _ in days]
    if next_position not in positions:
        next_position = positions[0]
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"▶ Start {dict(days)[next_position]}",
        callback_data=WkDay(position=next_position),
    )
    others = [(pos, name) for pos, name in days if pos != next_position]
    for pos, name in others:
        builder.button(text=name, callback_data=WkDay(position=pos))
    builder.button(text="Free workout", callback_data="wk_free")
    builder.adjust(1, *[2] * (len(others) // 2), *[1] * (len(others) % 2), 1)
    return builder.as_markup()


def workout_main_kb(
    plan_buttons: list[tuple[int, str]] | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, name in plan_buttons or []:
        builder.button(text=name, callback_data=WkPlanEx(index=index))
    builder.button(text="Add exercise", callback_data="wk_add_exercise")
    builder.button(text="Finish session", callback_data="wk_finish")
    builder.button(text="Cancel workout", callback_data="wk_cancel")
    builder.adjust(*[1] * len(plan_buttons or []), 2, 1)
    return builder.as_markup()


def exercise_choices_kb(exercises: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ex in exercises:
        builder.button(
            text=ex.name,
            callback_data=ExerciseChoice(exercise_id=ex.id).pack(),
        )
    builder.button(text="Cancel", callback_data="wk_cancel_exercise")
    builder.adjust(1)
    return builder.as_markup()


def set_entered_kb(has_notes: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Finish exercise", callback_data="wk_finish_exercise")
    if has_notes:
        builder.button(text="Remove note", callback_data="wk_remove_note")
    builder.button(text="Cancel exercise", callback_data="wk_cancel_exercise")
    builder.adjust(1)
    return builder.as_markup()


def finish_date_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Today", callback_data="wk_date_today")
    builder.button(text="Enter date", callback_data="wk_date_custom")
    builder.button(text="Back", callback_data="wk_back_to_main")
    builder.button(text="Cancel workout", callback_data="wk_cancel")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def finish_notes_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Skip", callback_data="wk_notes_skip")
    builder.button(text="Back", callback_data="wk_back_to_date")
    builder.button(text="Cancel workout", callback_data="wk_cancel")
    builder.adjust(1)
    return builder.as_markup()


def confirm_save_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Save workout", callback_data="wk_save")
    builder.button(text="Edit notes", callback_data="wk_edit_notes")
    builder.button(text="Cancel workout", callback_data="wk_cancel")
    builder.adjust(1)
    return builder.as_markup()


def cancel_confirm_kb() -> InlineKeyboardMarkup:
    return yes_no_kb("wk_cancel_confirm", "wk_cancel_abort")


def finish_confirm_kb() -> InlineKeyboardMarkup:
    # No — как у отмены: cb_cancel_abort вернёт кнопки окна тренировки
    return yes_no_kb("wk_finish_confirm", "wk_cancel_abort")
