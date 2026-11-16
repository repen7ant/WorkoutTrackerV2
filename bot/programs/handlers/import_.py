"""
Импорт программы: текст или .txt с первой строкой «# PROGRAM» в любой момент
вне ввода тренировки.

Мастер идёт на дорожке диалогов упражнений (ex_state), поэтому тренировку
можно начать посреди импорта, а импорт — не дожидаясь её конца.
"""

from contextlib import suppress
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.catalog.api import MUSCLES_PROMPT, Catalog, parse_muscle_names
from bot.catalog.service import add_exercise
from bot.filters import ExState
from bot.programs.domain import InvalidProgram, ProgramPlan, week_count
from bot.programs.draft import decode_txt, plan_from_fsm, plan_to_fsm
from bot.programs.keyboards import (
    IMPORT_PREFIX,
    ImportPick,
    confirm_kb,
    match_kb,
    muscles_kb,
)
from bot.programs.parser import PROGRAM_MARKER, parse_program
from bot.programs.service import (
    ExerciseNotAvailable,
    get_program,
    import_program,
    unmatched_names,
)
from bot.programs.states import ProgramImport
from bot.users.models import User
from bot.workouts.states import WorkoutSession

router = Router(name="program_import")

# текст, пока тренировка ждёт ввода, принадлежит ей: иначе программа ушла бы
# в заметку к упражнению
WORKOUT_IDLE = StateFilter(None, WorkoutSession.active)
# команды проходят дальше: /workout или /program посреди мастера — не поиск
NOT_COMMAND = ~F.text.startswith("/")
MAX_FILE_SIZE = 64 * 1024
# длиннее Telegram сам режет текст на несколько сообщений: начало программы
# пришло бы без конца
MAX_MESSAGE_LENGTH = 4000


def _question(name: str) -> str:
    return (
        f'Exercise "{name}" is not in your catalog. '
        "Pick a similar one, type a name to search, or create it:"
    )


def _summary(plan: ProgramPlan) -> str:
    count = len(plan.days)
    days = ", ".join(f"{day.name} ({len(day.exercises)})" for day in plan.days)
    return (
        f"Program: {week_count(plan.weeks)}, {count} day{'s' if count != 1 else ''}"
        f" — {days}.\nSave it?"
    )


async def _show(
    message: Message,
    ex_state: FSMContext,
    text: str,
    kb: InlineKeyboardMarkup,
    edit: bool = False,
) -> None:
    """Шаг мастера. Кнопки остаются только у последнего его сообщения."""
    if edit:
        with suppress(TelegramBadRequest):
            await message.edit_text(text, reply_markup=kb)
        await ex_state.update_data(wizard_msg_id=message.message_id)
        return
    old = (await ex_state.get_data()).get("wizard_msg_id")
    if old is not None:
        with suppress(TelegramBadRequest):
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id, message_id=old, reply_markup=None
            )
    sent = await message.answer(text, reply_markup=kb)
    await ex_state.update_data(wizard_msg_id=sent.message_id)


async def _next_step(
    message: Message,
    ex_state: FSMContext,
    session: AsyncSession,
    user: User,
    edit: bool = False,
) -> None:
    data = await ex_state.get_data()
    pending = data["pending"]
    if pending:
        await ex_state.set_state(ProgramImport.matching)
        similar = await Catalog(session).similar(pending[0], user.id)
        kb = match_kb(similar, left=len(pending))
        await _show(message, ex_state, _question(pending[0]), kb, edit)
        return
    await ex_state.set_state(ProgramImport.confirming)
    replacing = await get_program(session, user.id) is not None
    text = _summary(plan_from_fsm(data["plan"]))
    await _show(message, ex_state, text, confirm_kb(replacing), edit)


async def _resolve(ex_state: FSMContext, exercise_id: int) -> None:
    """Первое несопоставленное название — это упражнение каталога."""
    data = await ex_state.get_data()
    pending: list[str] = data["pending"]
    matched: dict[str, Any] = data["matched"]
    matched[pending.pop(0).casefold()] = exercise_id
    await ex_state.update_data(pending=pending, matched=matched)


async def _start(
    message: Message,
    text: str,
    ex_state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    try:
        plan = parse_program(text)
    except InvalidProgram as e:
        await message.answer(f"Can't import program.\n{e}")
        return
    names = [ex.name for day in plan.days for ex in day.exercises]
    found = await Catalog(session).by_names(names, user.id)
    # кнопки прошлого импорта снимет первый же шаг нового
    old = (await ex_state.get_data()).get("wizard_msg_id")
    await ex_state.set_data(
        {
            "plan": plan_to_fsm(plan),
            "matched": {name.casefold(): ex.id for name, ex in found.items()},
            "pending": unmatched_names(plan, found),
            "wizard_msg_id": old,
        }
    )
    await _next_step(message, ex_state, session, user)


@router.message(WORKOUT_IDLE, F.text.startswith(PROGRAM_MARKER))
async def on_program_text(
    message: Message, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    if len(message.text) >= MAX_MESSAGE_LENGTH:
        await message.answer(
            "The program is too long for one message: Telegram may have cut it."
            " Send it as a .txt file."
        )
        return
    await _start(message, message.text, ex_state, session, db_user)


@router.message(WORKOUT_IDLE, F.document.file_name.lower().endswith(".txt"))
async def on_program_file(
    message: Message, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    too_large = "File is too large (max 64 KB)."
    if (message.document.file_size or 0) > MAX_FILE_SIZE:
        await message.answer(too_large)
        return
    raw = (await message.bot.download(message.document)).read()
    if len(raw) > MAX_FILE_SIZE:
        await message.answer(too_large)
        return
    try:
        text = decode_txt(raw)
    except InvalidProgram as e:
        await message.answer(f"Can't import program.\n{e}")
        return
    await _start(message, text, ex_state, session, db_user)


@router.callback_query(ImportPick.filter(), ExState(ProgramImport.matching))
async def cb_pick(
    call: CallbackQuery,
    callback_data: ImportPick,
    ex_state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    if callback_data.left != len((await ex_state.get_data())["pending"]):
        # кнопка с прошлого шага: его название уже сопоставлено
        await call.answer()
        return
    exercise = await Catalog(session).get_visible(callback_data.exercise_id, db_user.id)
    if exercise is None:
        await call.answer("Exercise not found.", show_alert=True)
        return
    await _resolve(ex_state, exercise.id)
    await _next_step(call.message, ex_state, session, db_user, edit=True)
    await call.answer()


@router.message(ExState(ProgramImport.matching), WORKOUT_IDLE, F.text, NOT_COMMAND)
async def on_search(
    message: Message, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    pending = (await ex_state.get_data())["pending"]
    query = message.text.strip()
    found, _ = await Catalog(session).search(query, db_user.id, limit=5)
    text = _question(pending[0])
    if not found:
        text = f'Nothing found for "{query}".\n{text}'
    await _show(message, ex_state, text, match_kb(found, left=len(pending)))


@router.callback_query(F.data == "pi_create", ExState(ProgramImport.matching))
async def cb_create(call: CallbackQuery, ex_state: FSMContext) -> None:
    name = (await ex_state.get_data())["pending"][0]
    await ex_state.set_state(ProgramImport.entering_muscles)
    await _show(
        call.message,
        ex_state,
        f'New exercise "{name}".\n{MUSCLES_PROMPT}',
        muscles_kb(),
        edit=True,
    )
    await call.answer()


@router.message(
    ExState(ProgramImport.entering_muscles), WORKOUT_IDLE, F.text, NOT_COMMAND
)
async def on_muscles(
    message: Message, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    pending = (await ex_state.get_data())["pending"]
    name = pending[0]
    exercise = await add_exercise(
        session,
        name=name,
        user_id=db_user.id,
        muscle_names=parse_muscle_names(message.text),
    )
    if exercise is None:
        # каталог сравнивает без учёта регистра чуть иначе, чем мастер
        await ex_state.set_state(ProgramImport.matching)
        found, _ = await Catalog(session).search(name, db_user.id, limit=5)
        await _show(
            message,
            ex_state,
            f'Exercise "{name}" already exists. Pick it:',
            match_kb(found, left=len(pending)),
        )
        return
    await _resolve(ex_state, exercise.id)
    await _next_step(message, ex_state, session, db_user)


@router.callback_query(F.data == "pi_back", ExState(ProgramImport.entering_muscles))
async def cb_back(
    call: CallbackQuery, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    await _next_step(call.message, ex_state, session, db_user, edit=True)
    await call.answer()


@router.callback_query(F.data == "pi_save", ExState(ProgramImport.confirming))
async def cb_save(
    call: CallbackQuery, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    try:
        # снимаем сразу, чтобы двойной тап не сохранил дважды
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        await call.answer()
        return
    data = await ex_state.get_data()
    try:
        await import_program(
            session, db_user.id, plan_from_fsm(data["plan"]), data["matched"]
        )
    except ExerciseNotAvailable:
        await ex_state.clear()
        await call.message.edit_text(
            "One of the exercises was deleted meanwhile. Send the program again."
        )
        await call.answer()
        return
    except SQLAlchemyError:
        with suppress(TelegramBadRequest):
            await call.message.edit_reply_markup(
                reply_markup=confirm_kb(
                    await get_program(session, db_user.id) is not None
                )
            )
        raise
    await ex_state.clear()
    await call.message.edit_text("Program saved. Start it with /workout.")
    await call.answer()


@router.callback_query(F.data == "pi_cancel", ExState(ProgramImport))
async def cb_cancel(call: CallbackQuery, ex_state: FSMContext) -> None:
    await ex_state.clear()
    with suppress(TelegramBadRequest):
        await call.message.edit_text("Import cancelled.")
    await call.answer()


# последним: кнопки мастера, который уже закончился или сменился другим диалогом
@router.callback_query(F.data.startswith(IMPORT_PREFIX))
async def cb_stale(call: CallbackQuery) -> None:
    await call.answer(
        "This import has expired. Send the program again.", show_alert=True
    )
