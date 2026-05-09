from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.history import (
    HistoryDetail,
    HistoryPage,
    history_detail_kb,
    history_list_kb,
)
from bot.models.users import User
from bot.repositories.workout import WorkoutRepository
from bot.utils.formatters import format_workout_detail

router = Router(name="history")


async def send_history_page(
    target: Message | CallbackQuery,
    session: AsyncSession,
    user_id: int,
    page: int,
) -> None:
    repo = WorkoutRepository(session)
    workouts, total_pages = await repo.get_workouts_page(user_id, page)

    if not workouts:
        text = "No workouts yet."
        kb = None
    else:
        text = "<b>Workout history:</b>"
        kb = history_list_kb(workouts, page, total_pages)

    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.message(Command("history"))
async def cmd_history(message: Message, session: AsyncSession, db_user: User) -> None:
    await send_history_page(message, session, db_user.id, page=1)


@router.callback_query(HistoryPage.filter())
async def cb_history_page(
    call: CallbackQuery,
    callback_data: HistoryPage,
    session: AsyncSession,
    db_user: User,
) -> None:
    await send_history_page(call, session, db_user.id, page=callback_data.page)
    await call.answer()


@router.callback_query(F.data == "hist_noop")
async def cb_hist_noop(call: CallbackQuery) -> None:
    await call.answer()


@router.callback_query(HistoryDetail.filter())
async def cb_history_detail(
    call: CallbackQuery,
    callback_data: HistoryDetail,
    session: AsyncSession,
    db_user: User,
) -> None:
    repo = WorkoutRepository(session)
    workouts, _ = await repo.get_workouts_page(db_user.id, callback_data.page)
    workout = next((w for w in workouts if w.id == callback_data.workout_id), None)
    if workout is None:
        await call.answer("Workout not found.", show_alert=True)
        return
    exercises = await repo.get_workout_detail(callback_data.workout_id, db_user.id)
    text = format_workout_detail(workout, exercises)
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=history_detail_kb(callback_data.page),
    )
    await call.answer()
