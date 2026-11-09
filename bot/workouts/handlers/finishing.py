from contextlib import suppress
from datetime import date, datetime
from enum import Enum, auto

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.users.models import User
from bot.workouts.domain import InvalidWorkout
from bot.workouts.draft import build_record
from bot.workouts.formatters import format_confirm
from bot.workouts.handlers.common import BOT_COMMANDS, remove_kb, send_workout_main
from bot.workouts.keyboards import (
    cancel_confirm_kb,
    confirm_save_kb,
    finish_confirm_kb,
    finish_date_kb,
    finish_notes_kb,
    workout_main_kb,
)
from bot.workouts.service import ExerciseNotAvailable, record_workout
from bot.workouts.states import WorkoutSession

router = Router(name="workout_finishing")


class Step(Enum):
    DATE = auto()
    NOTES = auto()
    CONFIRM = auto()  # экран подтверждения с датой и заметкой
    YES_NO = auto()  # yes/no прямо в окне тренировки
    SAVE = auto()


def step_after_finish(ask_date: bool, ask_notes: bool) -> Step:
    if ask_date:
        return Step.DATE
    return Step.NOTES if ask_notes else Step.YES_NO


def step_after_date(ask_notes: bool, typed: bool) -> Step:
    if ask_notes:
        return Step.NOTES
    # введённую вручную дату показываем на проверку, «Today» сохраняем сразу
    return Step.CONFIRM if typed else Step.SAVE


async def _ask_notes(message: Message, state: FSMContext) -> None:
    await state.set_state(WorkoutSession.entering_notes)
    msg = await message.answer("Add notes or skip:", reply_markup=finish_notes_kb())
    await state.update_data(notes_prompt_msg_id=msg.message_id)


async def _show_confirm(message: Message, state: FSMContext) -> None:
    await state.set_state(WorkoutSession.confirming)
    await message.answer(
        format_confirm(await state.get_data()),
        parse_mode="HTML",
        reply_markup=confirm_save_kb(),
    )


async def _save(
    call: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user_id: int,
    restore_kb: InlineKeyboardMarkup,
) -> None:
    await remove_kb(call)  # снимаем сразу, чтобы двойной тап не сохранил дважды
    try:
        record = build_record(user_id, await state.get_data())
        await record_workout(session, record)
    except ExerciseNotAvailable:
        await _restore_kb(call, restore_kb)
        await call.answer(
            "One of the exercises was deleted. Cancel the workout or start it anew.",
            show_alert=True,
        )
        return
    except InvalidWorkout:
        await _restore_kb(call, restore_kb)
        await call.answer(
            "Workout data is invalid and can't be saved.", show_alert=True
        )
        return
    except SQLAlchemyError:
        # тренировка цела в FSM, но без кнопок с этого шага уже не выйти —
        # возвращаем их, а сообщить об ошибке дальше должен обработчик ошибок
        await _restore_kb(call, restore_kb)
        raise
    await state.clear()
    await call.message.answer(f"Workout saved ({record.date:%d-%m-%y}).")
    await call.answer()


async def _restore_kb(call: CallbackQuery, kb: InlineKeyboardMarkup) -> None:
    with suppress(TelegramBadRequest):
        await call.message.edit_reply_markup(reply_markup=kb)


# завершить тренировку
@router.callback_query(F.data == "wk_finish", WorkoutSession.active)
async def cb_finish(call: CallbackQuery, state: FSMContext, db_user: User) -> None:
    data = await state.get_data()
    if not data.get("exercises"):
        await call.answer("Add at least one exercise first.", show_alert=True)
        return
    match step_after_finish(db_user.ask_workout_date, db_user.ask_workout_notes):
        case Step.DATE:
            await state.set_state(WorkoutSession.finishing)
            await remove_kb(call)
            await call.message.answer(
                "Choose workout date:", reply_markup=finish_date_kb()
            )
        case Step.NOTES:
            await state.update_data(workout_date=date.today().isoformat())
            await remove_kb(call)
            await _ask_notes(call.message, state)
        case Step.YES_NO:
            # двойное нажатие: кнопки уже те же, Telegram ответит «not modified»
            with suppress(TelegramBadRequest):
                await call.message.edit_reply_markup(reply_markup=finish_confirm_kb())
    await call.answer()


# сохранить прямо из окна тренировки — дату и заметку не спрашивают
@router.callback_query(F.data == "wk_finish_confirm", WorkoutSession.active)
async def cb_finish_confirm(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    await state.update_data(workout_date=date.today().isoformat(), notes=None)
    await _save(call, state, session, db_user.id, restore_kb=workout_main_kb())


# назад в основное окно тренировки
@router.callback_query(F.data == "wk_back_to_main", WorkoutSession.finishing)
async def cb_back_to_main(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WorkoutSession.active)
    await send_workout_main(call, state)
    await call.answer()


# назад с заметки — к выбору даты, а если дату не спрашивают, к тренировке
@router.callback_query(F.data == "wk_back_to_date", WorkoutSession.entering_notes)
async def cb_back_to_date(
    call: CallbackQuery, state: FSMContext, db_user: User
) -> None:
    await state.update_data(workout_date=None, notes_prompt_msg_id=None, notes=None)
    if db_user.ask_workout_date:
        await state.set_state(WorkoutSession.finishing)
        await call.message.delete()
        await call.message.answer("Choose workout date:", reply_markup=finish_date_kb())
    else:
        await state.set_state(WorkoutSession.active)
        await send_workout_main(call, state)
    await call.answer()


# дата — сегодня
@router.callback_query(F.data == "wk_date_today", WorkoutSession.finishing)
async def cb_date_today(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    await state.update_data(workout_date=date.today().isoformat())
    match step_after_date(db_user.ask_workout_notes, typed=False):
        case Step.NOTES:
            await remove_kb(call)
            await _ask_notes(call.message, state)
            await call.answer()
        case Step.SAVE:
            await state.update_data(notes=None)
            await _save(call, state, session, db_user.id, restore_kb=finish_date_kb())


# дата — ввести вручную
@router.callback_query(F.data == "wk_date_custom", WorkoutSession.finishing)
async def cb_date_custom(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WorkoutSession.entering_date)
    await remove_kb(call)
    await call.message.answer("Enter date (DD-MM-YY):")
    await call.answer()


@router.message(WorkoutSession.entering_date, ~BOT_COMMANDS)
async def enter_date(message: Message, state: FSMContext, db_user: User) -> None:
    try:
        parsed_date = datetime.strptime(message.text.strip(), "%d-%m-%y").date()
    except ValueError:
        await message.delete()
        await message.answer("Invalid date. Use format DD-MM-YY:")
        return
    await message.delete()
    await state.update_data(workout_date=parsed_date.isoformat())
    match step_after_date(db_user.ask_workout_notes, typed=True):
        case Step.NOTES:
            await _ask_notes(message, state)
        case Step.CONFIRM:
            await state.update_data(notes=None)
            await _show_confirm(message, state)


# skip notes — к подтверждению
@router.callback_query(F.data == "wk_notes_skip", WorkoutSession.entering_notes)
async def cb_notes_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(notes=None)
    await remove_kb(call)
    await _show_confirm(call.message, state)
    await call.answer()


# notes entered — к подтверждению
@router.message(WorkoutSession.entering_notes, ~BOT_COMMANDS)
async def enter_notes(message: Message, state: FSMContext) -> None:
    await message.delete()
    await state.update_data(notes=message.text.strip())
    prompt_msg_id = (await state.get_data()).get("notes_prompt_msg_id")
    if prompt_msg_id:
        with suppress(TelegramBadRequest):
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id, message_id=prompt_msg_id, reply_markup=None
            )
    await _show_confirm(message, state)


# сохранять тренировку с окна подтверждения
@router.callback_query(F.data == "wk_save", WorkoutSession.confirming)
async def cb_save(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    await _save(call, state, session, db_user.id, restore_kb=confirm_save_kb())


# edit notes — назад к вводу заметок
@router.callback_query(F.data == "wk_edit_notes", WorkoutSession.confirming)
async def cb_edit_notes(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.delete()
    await _ask_notes(call.message, state)
    await call.answer()


# отменить всю тренировку
@router.callback_query(F.data == "wk_cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext) -> None:
    with suppress(TelegramBadRequest):
        await call.message.edit_reply_markup(reply_markup=cancel_confirm_kb())
    await call.answer()


@router.callback_query(F.data == "wk_cancel_confirm")
async def cb_cancel_confirm(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("Workout cancelled.", reply_markup=None)
    await call.answer()


@router.callback_query(F.data == "wk_cancel_abort")
async def cb_cancel_abort(call: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    if current == WorkoutSession.active:
        kb = workout_main_kb()
    elif current == WorkoutSession.finishing:
        kb = finish_date_kb()
    elif current == WorkoutSession.entering_date:
        await state.set_state(WorkoutSession.finishing)
        with suppress(TelegramBadRequest):
            await call.message.edit_reply_markup(reply_markup=None)
        await call.message.answer("Choose workout date:", reply_markup=finish_date_kb())
        await call.answer()
        return
    elif current == WorkoutSession.entering_notes:
        kb = finish_notes_kb()
    elif current == WorkoutSession.confirming:
        kb = confirm_save_kb()
    else:
        await call.answer()
        return
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer()
