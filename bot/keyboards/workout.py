from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class ExerciseChoice(CallbackData, prefix="wk_ex"):
    exercise_id: int
    exercise_name: str


def workout_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Add exercise", callback_data="wk_add_exercise")
    builder.button(text="Finish session", callback_data="wk_finish")
    builder.button(text="Cancel workout", callback_data="wk_cancel")
    builder.adjust(2, 1)
    return builder.as_markup()


def exercise_choices_kb(exercises: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ex in exercises:
        builder.button(
            text=ex.name,
            callback_data=ExerciseChoice(
                exercise_id=ex.id, exercise_name=ex.name
            ).pack(),
        )
    builder.button(text="Cancel", callback_data="wk_cancel_exercise")
    builder.adjust(1)
    return builder.as_markup()


def set_entered_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Finish exercise", callback_data="wk_finish_exercise")
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
