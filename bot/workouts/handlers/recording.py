from contextlib import suppress
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import Catalog
from bot.common.formatting import escape
from bot.programs.service import get_program
from bot.users.models import User
from bot.workouts.domain import (
    MAX_EXERCISE_NOTES,
    MAX_WEIGHT,
    InvalidWorkout,
    exercise_notes,
)
from bot.workouts.draft import seed_plan, set_to_fsm, sets_from_fsm, utc_now_iso
from bot.workouts.formatters import (
    format_current_sets,
    format_exercise_log,
    format_sets_prompt,
)
from bot.workouts.handlers.common import BOT_COMMANDS, remove_kb, send_workout_main
from bot.workouts.keyboards import (
    ExerciseChoice,
    WkDay,
    day_choice_kb,
    exercise_choices_kb,
    set_entered_kb,
)
from bot.workouts.repository import WorkoutRepository
from bot.workouts.set_parse import is_note, parse_set
from bot.workouts.states import WorkoutSession

router = Router(name="workout_recording")


# /workout
@router.message(Command("workout"))
async def cmd_workout(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    current = await state.get_state()
    if current is not None:
        await message.answer(
            "Workout is already in progress. Use the buttons to continue."
        )
        return
    program = await get_program(session, db_user.id)
    if program is None:
        await _start_workout(state)
        await send_workout_main(message, state)
        return
    days = [(day.position, day.name) for day in program.days]
    kb = day_choice_kb(days, program.next_position)
    # подпись первой кнопки — тот день, который предложит клавиатура
    next_name = kb.inline_keyboard[0][0].text.removeprefix("▶ Start ")
    await message.answer(
        f"Next up: <b>{escape(next_name)}</b>. Start it or pick another day:",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def _start_workout(state: FSMContext, **plan: Any) -> None:
    await state.set_state(WorkoutSession.active)
    await state.update_data(exercises=[], started_at=utc_now_iso(), **plan)


# день программы
@router.callback_query(WkDay.filter())
async def cb_day(
    call: CallbackQuery,
    callback_data: WkDay,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    if await state.get_state() is not None:
        # второй тап или старая кнопка: тренировка уже идёт
        await call.answer()
        return
    program = await get_program(session, db_user.id)
    if program is None or callback_data.position not in {
        day.position for day in program.days
    }:
        await call.answer(
            "The program has changed. Use /workout again.", show_alert=True
        )
        return
    plan: dict[str, Any] = {}
    seed_plan(plan, program, callback_data.position)
    await _start_workout(state, **plan)
    await send_workout_main(call, state)
    await call.answer()


# тренировка без программы
@router.callback_query(F.data == "wk_free")
async def cb_free(call: CallbackQuery, state: FSMContext) -> None:
    if await state.get_state() is not None:
        await call.answer()
        return
    await _start_workout(state)
    await send_workout_main(call, state)
    await call.answer()


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
    log_size = db_user.exercise_log_size
    if log_size:
        log = await WorkoutRepository(session).with_exercise(
            exercise_id=exercise.id, user_id=db_user.id, limit=log_size
        )
    await remove_kb(call)
    if log_size:
        await call.message.answer(
            format_exercise_log(exercise.name, log), parse_mode="HTML"
        )
        prompt = format_sets_prompt()
    else:
        # без лога название упражнения больше нигде не видно
        prompt = format_sets_prompt(exercise.name)
    sent = await call.message.answer(
        prompt, parse_mode="HTML", reply_markup=set_entered_kb()
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
