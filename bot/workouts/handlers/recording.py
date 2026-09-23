from contextlib import suppress
from decimal import Decimal, InvalidOperation
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog
from bot.users.models import User
from bot.workouts.domain import MAX_WEIGHT, SetEntry
from bot.workouts.draft import set_to_fsm, sets_from_fsm
from bot.workouts.formatters import format_current_sets, format_exercise_log
from bot.workouts.handlers.common import BOT_COMMANDS, remove_kb, send_workout_main
from bot.workouts.keyboards import (
    ExerciseChoice,
    exercise_choices_kb,
    set_entered_kb,
)
from bot.workouts.repository import WorkoutRepository
from bot.workouts.states import WorkoutSession

router = Router(name="workout_recording")


def parse_set(text: str | None) -> SetEntry | None:
    """Разбирает '100x5' или 'BWx10'. Допустимость значений решает SetEntry."""
    # в состоянии ввода подходов может прилететь стикер или фото — там text is None
    if not text:
        return None
    parts = text.strip().upper().split("X")
    if len(parts) != 2:
        return None
    weight_str, reps_str = parts
    try:
        reps = int(reps_str)
        weight = None if weight_str == "BW" else Decimal(weight_str)
        return SetEntry.create(weight, reps)
    except (ValueError, InvalidOperation):
        # InvalidWorkout — тоже ValueError
        return None


# /workout
@router.message(Command("workout"))
async def cmd_workout(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is not None:
        await message.answer(
            "Workout is already in progress. Use the buttons to continue."
        )
        return
    await state.set_state(WorkoutSession.active)
    await state.update_data(exercises=[])
    await send_workout_main(message, state)


# добавить упражнение
@router.callback_query(F.data == "wk_add_exercise", WorkoutSession.active)
async def cb_add_exercise(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WorkoutSession.choosing_exercise)
    await remove_kb(call)
    await call.message.answer("Enter exercise name:")
    await call.answer()


# поиск упражнения по вводу
@router.message(WorkoutSession.choosing_exercise)
async def choose_exercise(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    exercises, total = await Catalog(session).search(message.text, db_user.id)
    await message.delete()
    if not exercises:
        await message.answer("Nothing found. Try again:")
        return
    header = (
        f"Select exercise (showing {len(exercises)} of {total}, refine the search):"
        if total > len(exercises)
        else "Select exercise:"
    )
    await message.answer(header, reply_markup=exercise_choices_kb(exercises))


# выбор упражнения из списка
@router.callback_query(ExerciseChoice.filter(), WorkoutSession.choosing_exercise)
async def cb_exercise_chosen(
    call: CallbackQuery,
    callback_data: ExerciseChoice,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    exercise = await Catalog(session).get_visible(callback_data.exercise_id, db_user.id)
    if exercise is None:
        await call.answer("Exercise not found.", show_alert=True)
        return
    log = await WorkoutRepository(session).with_exercise(
        exercise_id=exercise.id, user_id=db_user.id, limit=10
    )
    await remove_kb(call)
    await call.message.answer(
        format_exercise_log(exercise.name, log), parse_mode="HTML"
    )
    sent = await call.message.answer(
        "Enter set (e.g. <code>100x5</code> or <code>BWx10</code>):",
        parse_mode="HTML",
        reply_markup=set_entered_kb(),
    )
    await state.set_state(WorkoutSession.entering_sets)
    await state.update_data(
        current_exercise_id=exercise.id,
        current_exercise_name=exercise.name,
        current_sets=[],
        sets_message_id=sent.message_id,
        last_msg_id=sent.message_id,
    )
    await call.answer()


async def show_sets(
    message: Message,
    state: FSMContext,
    data: dict[str, Any],
    text: str,
    user_message_deleted: bool,
) -> None:
    """
    Показывает список подходов, удерживая его внизу чата.

    Пока промпт — последнее сообщение, правим его на месте: так ничего не мигает.
    Но между промптом и вводом могло что-то вклиниться — /exercises, /history,
    ошибка формата, неудалённое сообщение самого пользователя. Тогда промпт
    уехал вверх, и правка в нём пользователю не видна: он вводит подход и не
    получает никакого отклика. В этом случае пересоздаём сообщение внизу.
    """
    prompt_id = data["sets_message_id"]
    # message_id внутри чата идут подряд: если ввод пришёл следующим номером,
    # значит после промпта никто больше ничего не присылал
    still_last = (
        user_message_deleted
        and message.message_id == data.get("last_msg_id", prompt_id) + 1
    )
    if still_last:
        with suppress(TelegramBadRequest):
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_id,
                text=text,
                parse_mode="HTML",
                reply_markup=set_entered_kb(),
            )
            await state.update_data(last_msg_id=message.message_id)
            return

    with suppress(TelegramBadRequest):
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
    sent = await message.answer(text, parse_mode="HTML", reply_markup=set_entered_kb())
    await state.update_data(
        sets_message_id=sent.message_id, last_msg_id=sent.message_id
    )


# ввод подхода
@router.message(WorkoutSession.entering_sets, ~BOT_COMMANDS)
async def enter_set(message: Message, state: FSMContext) -> None:
    entry = parse_set(message.text)
    if entry is None:
        await message.answer(
            "Invalid set. Use <code>100x5</code> or <code>BWx10</code>"
            f" (weight up to {MAX_WEIGHT}):",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    current_sets = data.get("current_sets", [])
    current_sets.append(set_to_fsm(entry))
    await state.update_data(current_sets=current_sets)

    # Telegram не даёт боту удалять сообщения старше 48 часов: если тренировку
    # оставили открытой на двое суток, сообщение останется в чате ниже промпта
    try:
        await message.delete()
    except TelegramBadRequest:
        deleted = False
    else:
        deleted = True

    await show_sets(
        message,
        state,
        data,
        format_current_sets(sets_from_fsm(current_sets)),
        user_message_deleted=deleted,
    )


# завершить упражнение
@router.callback_query(F.data == "wk_finish_exercise", WorkoutSession.entering_sets)
async def cb_finish_exercise(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("current_sets"):
        await call.answer("Add at least one set first.", show_alert=True)
        return
    exercises = data.get("exercises", [])
    exercises.append(
        {
            "exercise_id": data["current_exercise_id"],
            "exercise_name": data["current_exercise_name"],
            "sets": data["current_sets"],
        }
    )
    await state.update_data(
        exercises=exercises,
        current_exercise_id=None,
        current_exercise_name=None,
        current_sets=[],
    )
    await state.set_state(WorkoutSession.active)
    await remove_kb(call)
    await call.answer()
    await send_workout_main(call, state)


# отменить текущее упражнение
@router.callback_query(F.data == "wk_cancel_exercise")
async def cb_cancel_exercise(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(
        current_exercise_id=None,
        current_exercise_name=None,
        current_sets=[],
    )
    await state.set_state(WorkoutSession.active)
    await remove_kb(call)
    await call.answer()
    await send_workout_main(call, state)
