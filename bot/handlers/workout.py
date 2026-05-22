from datetime import date, datetime
from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.workout import (
    ExerciseChoice,
    cancel_confirm_kb,
    confirm_save_kb,
    exercise_choices_kb,
    finish_date_kb,
    finish_notes_kb,
    set_entered_kb,
    workout_main_kb,
)
from bot.models.users import User
from bot.repositories.exercise import ExerciseRepository
from bot.repositories.workout import WorkoutRepository
from bot.states.workout import WorkoutSession
from bot.utils.formatters import format_exercise_log

router = Router(name="workout")


def parse_set(text: str) -> tuple[Decimal | None, int] | None:
    """Парсит '100x5' или 'BWx10'. Возвращает (weight, reps) или None."""
    try:
        parts = text.strip().upper().split("X")
        if len(parts) != 2:
            return None
        weight_str, reps_str = parts
        reps = int(reps_str)
        if reps <= 0:
            return None
        if weight_str == "BW":
            return None, reps
        weight = Decimal(weight_str)
        if weight < 0:
            return None
        return weight, reps
    except Exception:
        return None


async def send_workout_main(target: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    exercises = data.get("exercises", [])

    if exercises:
        lines = ["<b>Current workout:</b>\n"]
        for ex in exercises:
            lines.append(f"<b>{ex['exercise_name']}</b>")
            for i, s in enumerate(ex["sets"], start=1):
                weight = "BW" if s["weight"] is None else f"{s['weight']}kg"
                lines.append(f"  {i}. {weight} x {s['reps']}")
            lines.append("")
        text = "\n".join(lines)
    else:
        text = "Workout started. Add your first exercise."

    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=workout_main_kb())
    else:
        await target.message.edit_text(
            text, parse_mode="HTML", reply_markup=workout_main_kb()
        )


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
    repo = ExerciseRepository(session)
    exercises = await repo.search_by_name(message.text, db_user.id)
    await message.delete()
    if not exercises:
        await message.answer("Nothing found. Try again:")
        return
    await message.answer(
        "Select exercise:", reply_markup=exercise_choices_kb(exercises)
    )


# выбор упражнения из списка
@router.callback_query(ExerciseChoice.filter(), WorkoutSession.choosing_exercise)
async def cb_exercise_chosen(
    call: CallbackQuery,
    callback_data: ExerciseChoice,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    repo = ExerciseRepository(session)
    log = await repo.get_exercise_log(
        exercise_id=callback_data.exercise_id,
        user_id=db_user.id,
        limit=20,
    )
    log_text = format_exercise_log(callback_data.exercise_name, log)
    await remove_kb(call)
    await call.message.answer(log_text, parse_mode="HTML")
    sent = await call.message.answer(
        "Enter set (e.g. <code>100x5</code> or <code>BWx10</code>):",
        parse_mode="HTML",
        reply_markup=set_entered_kb(),
    )
    await state.set_state(WorkoutSession.entering_sets)
    await state.update_data(
        current_exercise_id=callback_data.exercise_id,
        current_exercise_name=callback_data.exercise_name,
        current_sets=[],
        sets_message_id=sent.message_id,
    )
    await call.answer()


# ввод подхода
@router.message(WorkoutSession.entering_sets)
async def enter_set(message: Message, state: FSMContext) -> None:
    parsed = parse_set(message.text)
    if parsed is None:
        await message.answer(
            "Invalid format. Use <code>100x5</code> or <code>BWx10</code>:",
            parse_mode="HTML",
        )
        return

    weight, reps = parsed
    data = await state.get_data()
    current_sets = data.get("current_sets", [])
    current_sets.append({"weight": weight, "reps": reps})
    await state.update_data(current_sets=current_sets)

    lines = []
    for i, s in enumerate(current_sets, start=1):
        w = "BW" if s["weight"] is None else f"{s['weight']}kg"
        lines.append(f"  {i}. {w} x {s['reps']}")
    text = "\n".join(lines) + "\n\nEnter next set or finish exercise:"

    await message.delete()  # удаляем сообщение пользователя
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=data["sets_message_id"],
        text=text,
        parse_mode="HTML",
        reply_markup=set_entered_kb(),
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


# завершить тренировку
@router.callback_query(F.data == "wk_finish", WorkoutSession.active)
async def cb_finish(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("exercises"):
        await call.answer("Add at least one exercise first.", show_alert=True)
        return
    await state.set_state(WorkoutSession.finishing)
    await remove_kb(call)
    await call.message.answer("Choose workout date:", reply_markup=finish_date_kb())
    await call.answer()


# назад в основное окно тренировки
@router.callback_query(F.data == "wk_back_to_main", WorkoutSession.finishing)
async def cb_back_to_main(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WorkoutSession.active)
    await send_workout_main(call, state)
    await call.answer()


# назад к выбору даты
@router.callback_query(F.data == "wk_back_to_date", WorkoutSession.entering_notes)
async def cb_back_to_date(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(workout_date=None, notes_prompt_msg_id=None, notes=None)
    await state.set_state(WorkoutSession.finishing)
    await call.message.delete()
    await call.message.answer("Choose workout date:", reply_markup=finish_date_kb())
    await call.answer()


# дата — сегодня
@router.callback_query(F.data == "wk_date_today", WorkoutSession.finishing)
async def cb_date_today(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(workout_date=date.today().isoformat())
    await state.set_state(WorkoutSession.entering_notes)
    await remove_kb(call)

    msg = await call.message.answer(
        "Add notes or skip:", reply_markup=finish_notes_kb()
    )
    await state.update_data(notes_prompt_msg_id=msg.message_id)

    await call.answer()


# дата — ввести вручную
@router.callback_query(F.data == "wk_date_custom", WorkoutSession.finishing)
async def cb_date_custom(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WorkoutSession.entering_date)
    await remove_kb(call)
    await call.message.answer("Enter date (DD-MM-YY):")
    await call.answer()


@router.message(WorkoutSession.entering_date)
async def enter_date(message: Message, state: FSMContext) -> None:
    try:
        parsed_date = datetime.strptime(message.text.strip(), "%d-%m-%y").date()
    except ValueError:
        await message.delete()
        await message.answer("Invalid date. Use format DD-MM-YY:")
        return
    await message.delete()
    await state.update_data(workout_date=parsed_date.isoformat())
    await state.set_state(WorkoutSession.entering_notes)

    msg = await message.answer("Add notes or skip:", reply_markup=finish_notes_kb())
    await state.update_data(notes_prompt_msg_id=msg.message_id)


def build_confirm_text(data: dict[str, Any]) -> str:
    workout_date_raw = data.get("workout_date")
    workout_date = (
        date.fromisoformat(workout_date_raw).strftime("%d-%m-%y")
        if workout_date_raw
        else "—"
    )
    notes = data.get("notes") or "—"
    return f"<b>Date:</b> {workout_date}\n<b>Notes:</b> {notes}\n\nSave workout?"


# skip notes — к подтверждению
@router.callback_query(F.data == "wk_notes_skip", WorkoutSession.entering_notes)
async def cb_notes_skip(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(notes=None)
    await state.set_state(WorkoutSession.confirming)
    await remove_kb(call)
    await call.message.answer(
        build_confirm_text(await state.get_data()),
        parse_mode="HTML",
        reply_markup=confirm_save_kb(),
    )
    await call.answer()


# notes entered — к подтверждению
@router.message(WorkoutSession.entering_notes)
async def enter_notes(message: Message, state: FSMContext) -> None:
    await message.delete()
    await state.update_data(notes=message.text.strip())
    await state.set_state(WorkoutSession.confirming)
    data = await state.get_data()
    prompt_msg_id = data.get("notes_prompt_msg_id")
    if prompt_msg_id:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id, message_id=prompt_msg_id, reply_markup=None
            )
        except Exception:
            pass
    await message.answer(
        build_confirm_text(data),
        parse_mode="HTML",
        reply_markup=confirm_save_kb(),
    )


# сохранять тренировку с окна подтверждения
@router.callback_query(F.data == "wk_save", WorkoutSession.confirming)
async def cb_save(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    await remove_kb(call)
    await save_and_finish(call.message, state, session, db_user)
    await call.answer()


# edit notes — назад к вводу заметок
@router.callback_query(F.data == "wk_edit_notes", WorkoutSession.confirming)
async def cb_edit_notes(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(WorkoutSession.entering_notes)
    await call.message.delete()
    msg = await call.message.answer(
        "Add notes or skip:", reply_markup=finish_notes_kb()
    )
    await state.update_data(notes_prompt_msg_id=msg.message_id)
    await call.answer()


async def save_and_finish(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    data = await state.get_data()
    repo = WorkoutRepository(session)
    await repo.save_workout(
        user_id=db_user.id,
        workout_date=date.fromisoformat(data["workout_date"]),
        notes=data.get("notes"),
        exercises=data["exercises"],
    )
    await state.clear()
    await message.answer("Workout saved.")


# отменить всю тренировку
@router.callback_query(F.data == "wk_cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext) -> None:
    try:
        await call.message.edit_reply_markup(reply_markup=cancel_confirm_kb())
    except Exception:
        pass
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
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
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


async def remove_kb(call: CallbackQuery) -> None:
    await call.message.edit_reply_markup(reply_markup=None)
