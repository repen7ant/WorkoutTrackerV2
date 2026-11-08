import re
from contextlib import suppress
from decimal import Decimal, InvalidOperation
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog
from bot.users.models import User
from bot.workouts.domain import (
    MAX_EXERCISE_NOTES,
    MAX_WEIGHT,
    InvalidWorkout,
    SetEntry,
    exercise_notes,
)
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

# после upper(): «1:30» — минуты:секунды, «45S» — секунды
_MIN_SEC = re.compile(r"(\d+):([0-5]\d)")
_SEC = re.compile(r"(\d+)S")
# после upper(): русская «Х» вместо X и запятая в весе — с телефона так пишут часто
_SET_TYPOS = str.maketrans({"\u0425": "X", ",": "."})
# буквы формата подхода после upper(): X и русская Х, BW, S у секунд
_SET_LETTERS = frozenset("XBWS\u0425")


def is_note(text: str | None) -> bool:
    """
    Заметка — текст со словами. Текст без них — попытка ввести подход, даже
    с опечаткой («100 5», «100x»): на него нужна подсказка формата, а не заметка.
    """
    return bool(text) and any(
        ch.isalpha() and ch not in _SET_LETTERS for ch in text.upper()
    )


def _parse_seconds(text: str) -> int | None:
    if m := _MIN_SEC.fullmatch(text):
        return int(m[1]) * 60 + int(m[2])
    if m := _SEC.fullmatch(text):
        return int(m[1])
    return None


def parse_set(text: str | None) -> SetEntry | None:
    """Разбирает '100x5', 'BWx10' или время: 'BWx1:30', '20x45s'.
    Допустимость значений решает SetEntry."""
    # в состоянии ввода подходов может прилететь стикер или фото — там text is None
    if not text:
        return None
    parts = text.strip().upper().translate(_SET_TYPOS).split("X")
    if len(parts) != 2:
        return None
    weight_str, amount_str = parts
    try:
        weight = None if weight_str == "BW" else Decimal(weight_str)
        seconds = _parse_seconds(amount_str)
        if seconds is not None:
            return SetEntry.create(weight, seconds=seconds)
        return SetEntry.create(weight, reps=int(amount_str))
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
        "Enter set (e.g. <code>100x5</code>, <code>BWx10</code>"
        " or time <code>BWx1:30</code> / <code>BWx90s</code>)"
        " or any text to add a note:",
        parse_mode="HTML",
        reply_markup=set_entered_kb(),
    )
    await state.set_state(WorkoutSession.entering_sets)
    await state.update_data(
        current_exercise_id=exercise.id,
        current_exercise_name=exercise.name,
        current_sets=[],
        current_notes=None,
        sets_message_id=sent.message_id,
        last_msg_id=sent.message_id,
    )
    await call.answer()


def _sets_view(data: dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    # у тренировки, начатой до заметок к упражнениям, ключа current_notes нет
    notes = data.get("current_notes")
    text = format_current_sets(
        data["current_exercise_name"],
        notes,
        sets_from_fsm(data.get("current_sets", [])),
    )
    return text, set_entered_kb(has_notes=bool(notes))


async def show_sets(
    message: Message, state: FSMContext, user_message_deleted: bool
) -> None:
    """
    Показывает подходы и заметку текущего упражнения, удерживая их внизу чата.

    Пока промпт — последнее сообщение, правим его на месте: так ничего не мигает.
    Но между промптом и вводом могло что-то вклиниться — /exercises, /history,
    ошибка формата, неудалённое сообщение самого пользователя. Тогда промпт
    уехал вверх, и правка в нём пользователю не видна: он вводит подход и не
    получает никакого отклика. В этом случае пересоздаём сообщение внизу.
    """
    data = await state.get_data()
    text, kb = _sets_view(data)
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
                reply_markup=kb,
            )
            await state.update_data(last_msg_id=message.message_id)
            return

    with suppress(TelegramBadRequest):
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
    sent = await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.update_data(
        sets_message_id=sent.message_id, last_msg_id=sent.message_id
    )


# ввод подхода или заметки к упражнению
@router.message(WorkoutSession.entering_sets, ~BOT_COMMANDS)
async def enter_set(message: Message, state: FSMContext) -> None:
    if is_note(message.text):
        try:
            notes = exercise_notes(message.text)
        except InvalidWorkout:
            # сообщение не удаляем: его можно скопировать и сократить
            await message.answer(
                f"Note is too long (max {MAX_EXERCISE_NOTES} characters)."
            )
            return
        await state.update_data(current_notes=notes)
    else:
        entry = parse_set(message.text)
        if entry is None:
            await message.answer(
                "Invalid set. Use <code>100x5</code>, <code>BWx10</code>"
                " or time <code>BWx1:30</code> / <code>BWx90s</code>"
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

    await show_sets(message, state, user_message_deleted=deleted)


# убрать заметку к упражнению
@router.callback_query(F.data == "wk_remove_note", WorkoutSession.entering_sets)
async def cb_remove_note(call: CallbackQuery, state: FSMContext) -> None:
    # при двойном нажатии заметку уже убрало первое
    if (await state.get_data()).get("current_notes"):
        await state.update_data(current_notes=None)
        text, kb = _sets_view(await state.get_data())
        with suppress(TelegramBadRequest):
            await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


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
            "notes": data.get("current_notes"),
        }
    )
    await state.update_data(
        exercises=exercises,
        current_exercise_id=None,
        current_exercise_name=None,
        current_sets=[],
        current_notes=None,
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
        current_notes=None,
    )
    await state.set_state(WorkoutSession.active)
    await remove_kb(call)
    await call.answer()
    await send_workout_main(call, state)
