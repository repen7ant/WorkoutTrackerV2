from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class ExercisePage(CallbackData, prefix="ex_page"):
    page: int


class ExerciseFilter(CallbackData, prefix="ex_filter"):
    muscle_id: int


class ExerciseDelete(CallbackData, prefix="ex_delete"):
    exercise_id: int


class ExerciseDeleteConfirm(CallbackData, prefix="ex_delete_confirm"):
    exercise_id: int


def exercises_menu_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text="Search", callback_data="ex_search")
    builder.button(text="Filter by muscle", callback_data="ex_filter_menu")
    builder.button(text="Add", callback_data="ex_add")
    builder.button(text="Delete", callback_data="ex_delete_menu")
    builder.adjust(2)

    nav = []
    if page > 1:
        nav.append(("←", ExercisePage(page=page - 1).pack()))
    nav.append((f"{page}/{total_pages}", "ex_noop"))
    if page < total_pages:
        nav.append(("→", ExercisePage(page=page + 1).pack()))

    for text, data in nav:
        builder.button(text=text, callback_data=data)
    builder.adjust(2, 2, len(nav))

    return builder.as_markup()


def muscles_filter_kb(muscles: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for muscle in muscles:
        builder.button(
            text=muscle.name,
            callback_data=ExerciseFilter(muscle_id=muscle.id).pack(),
        )
    builder.button(text="Cancel", callback_data="ex_filter_cancel")
    builder.adjust(2)
    return builder.as_markup()


def delete_exercises_kb(exercises: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ex in exercises:
        builder.button(
            text=ex.name,
            callback_data=ExerciseDelete(exercise_id=ex.id).pack(),
        )
    builder.button(text="Cancel", callback_data="ex_delete_cancel")
    builder.adjust(1)
    return builder.as_markup()


def delete_confirm_kb(exercise_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Yes, delete",
        callback_data=ExerciseDeleteConfirm(exercise_id=exercise_id).pack(),
    )
    builder.button(text="Cancel", callback_data="ex_delete_cancel")
    builder.adjust(2)
    return builder.as_markup()


def search_result_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Back to all exercises", callback_data="ex_back")
    builder.button(text="Search again", callback_data="ex_search")
    builder.adjust(1)
    return builder.as_markup()
