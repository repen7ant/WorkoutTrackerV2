from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.formatters import format_exercise_list
from bot.catalog.keyboards import (
    ExerciseDelete,
    ExerciseDeleteConfirm,
    ExerciseFilter,
    ExercisePage,
    delete_confirm_kb,
    delete_exercises_kb,
    exercises_menu_kb,
    muscles_filter_kb,
    search_result_kb,
)
from bot.catalog.repository import ExerciseRepository
from bot.catalog.states import ExerciseAdd, ExerciseSearch
from bot.filters import ExState
from bot.users.models import User
from bot.workouts.states import WorkoutSession

router = Router(name="exercises")
PER_PAGE = 20

# Диалоги упражнений живут на своей FSM-дорожке (ex_state) и не трогают
# состояние тренировки. Но текстовое сообщение — общий ресурс: если тренировка
# ждёт ввод, он принадлежит ей. В WorkoutSession.active тренировка управляется
# кнопками, текст ей не нужен.
WORKOUT_IDLE = StateFilter(None, WorkoutSession.active)


async def send_exercise_page(
    target: Message | CallbackQuery,
    session: AsyncSession,
    page: int,
    user_id: int,
) -> None:
    repo = ExerciseRepository(session)
    exercises, total_pages = await repo.get_page(page, user_id, PER_PAGE)
    offset = (page - 1) * PER_PAGE
    text = format_exercise_list(exercises, offset=offset)
    kb = exercises_menu_kb(page, total_pages)

    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# /exercises
@router.message(Command("exercises"))
async def cmd_exercises(message: Message, session: AsyncSession, db_user: User) -> None:
    await send_exercise_page(message, session, page=1, user_id=db_user.id)


# пагинация
@router.callback_query(ExercisePage.filter())
async def cb_page(
    call: CallbackQuery,
    callback_data: ExercisePage,
    session: AsyncSession,
    db_user: User,
) -> None:
    await send_exercise_page(call, session, page=callback_data.page, user_id=db_user.id)
    await call.answer()


# заглушка для кнопки текущей страницы
@router.callback_query(F.data == "ex_noop")
async def cb_noop(call: CallbackQuery) -> None:
    await call.answer()


# поиск
@router.callback_query(F.data == "ex_search")
async def cb_search(call: CallbackQuery, ex_state: FSMContext) -> None:
    await ex_state.set_state(ExerciseSearch.waiting_query)
    await call.message.answer("Enter exercise name:")
    await call.answer()


@router.message(ExState(ExerciseSearch.waiting_query), WORKOUT_IDLE)
async def search_query(
    message: Message, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    repo = ExerciseRepository(session)
    exercises, total = await repo.search_by_name(message.text, db_user.id)
    await ex_state.clear()
    if not exercises:
        await message.answer("Nothing found.", reply_markup=search_result_kb())
        return
    text = format_exercise_list(exercises)
    if total > len(exercises):
        text += f"\n\nShowing {len(exercises)} of {total}. Refine the search."
    await message.answer(text, parse_mode="HTML", reply_markup=search_result_kb())


# фильтр по мышцам
@router.callback_query(F.data == "ex_filter_menu")
async def cb_filter_menu(
    call: CallbackQuery, session: AsyncSession, db_user: User
) -> None:
    repo = ExerciseRepository(session)
    muscles = await repo.get_all_muscles(db_user.id)
    await call.message.edit_reply_markup(reply_markup=muscles_filter_kb(muscles))
    await call.answer()


@router.callback_query(ExerciseFilter.filter())
async def cb_filter(
    call: CallbackQuery,
    callback_data: ExerciseFilter,
    session: AsyncSession,
    db_user: User,
) -> None:
    repo = ExerciseRepository(session)
    exercises = await repo.filter_by_muscle_id(callback_data.muscle_id, db_user.id)
    text = format_exercise_list(exercises)
    await call.message.edit_text(
        text, parse_mode="HTML", reply_markup=exercises_menu_kb(1, 1)
    )
    await call.answer()


@router.callback_query(F.data == "ex_filter_cancel")
async def cb_filter_cancel(
    call: CallbackQuery, session: AsyncSession, db_user: User
) -> None:
    await send_exercise_page(call, session, page=1, user_id=db_user.id)
    await call.answer()


# добавление
@router.callback_query(F.data == "ex_add")
async def cb_add(call: CallbackQuery, ex_state: FSMContext) -> None:
    await ex_state.set_state(ExerciseAdd.waiting_name)
    await call.message.answer("Enter exercise name:")
    await call.answer()


@router.message(ExState(ExerciseAdd.waiting_name), WORKOUT_IDLE)
async def add_name(message: Message, ex_state: FSMContext) -> None:
    await ex_state.update_data(name=message.text.strip())
    await ex_state.set_state(ExerciseAdd.waiting_muscles)
    await message.answer(
        "Enter muscles separated by comma (e.g. Chest, Tricep):\nor send — to skip"
    )


@router.message(ExState(ExerciseAdd.waiting_muscles), WORKOUT_IDLE)
async def add_muscles(
    message: Message, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    data = await ex_state.get_data()
    repo = ExerciseRepository(session)
    muscle_names = (
        []
        if message.text.strip() == "—"
        else [m.strip() for m in message.text.split(",")]
    )
    exercise = await repo.add(
        name=data["name"], user_id=db_user.id, muscle_names=muscle_names
    )
    await ex_state.clear()
    if exercise is None:
        await message.answer(
            f"Exercise <b>{data['name']}</b> already exists.", parse_mode="HTML"
        )
    else:
        await message.answer(
            f"Exercise <b>{data['name']}</b> added.", parse_mode="HTML"
        )
    await send_exercise_page(message, session, page=1, user_id=db_user.id)


# удаление
@router.callback_query(F.data == "ex_delete_menu")
async def cb_delete_menu(
    call: CallbackQuery, session: AsyncSession, db_user: User
) -> None:
    repo = ExerciseRepository(session)
    exercises = await repo.get_user_exercises(db_user.id)
    if not exercises:
        await call.answer("You have no custom exercises.", show_alert=True)
        return
    await call.message.answer(
        "Select exercise to delete:",
        reply_markup=delete_exercises_kb(exercises),
    )
    await call.answer()


@router.callback_query(ExerciseDelete.filter())
async def cb_delete(
    call: CallbackQuery,
    callback_data: ExerciseDelete,
    session: AsyncSession,
    db_user: User,
) -> None:
    repo = ExerciseRepository(session)
    exercise = await repo.get_own(callback_data.exercise_id, db_user.id)
    if exercise is None:
        await call.answer("Exercise not found or access denied.", show_alert=True)
        return
    await call.message.edit_text(
        f"Delete <b>{exercise.name}</b>?",
        parse_mode="HTML",
        reply_markup=delete_confirm_kb(callback_data.exercise_id),
    )
    await call.answer()


@router.callback_query(ExerciseDeleteConfirm.filter())
async def cb_delete_confirm(
    call: CallbackQuery,
    callback_data: ExerciseDeleteConfirm,
    session: AsyncSession,
    db_user: User,
) -> None:
    repo = ExerciseRepository(session)
    deleted = await repo.delete(callback_data.exercise_id, db_user.id)
    if deleted:
        await call.message.edit_text("Exercise deleted.")
    else:
        await call.message.edit_text("Exercise not found or access denied.")
    await call.answer()
    await send_exercise_page(call.message, session, page=1, user_id=db_user.id)


@router.callback_query(F.data == "ex_delete_cancel")
async def cb_delete_cancel(
    call: CallbackQuery, session: AsyncSession, db_user: User
) -> None:
    await send_exercise_page(call, session, page=1, user_id=db_user.id)
    await call.answer()


@router.callback_query(F.data == "ex_back")
async def cb_back(call: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    await send_exercise_page(call, session, page=1, user_id=db_user.id)
    await call.answer()
