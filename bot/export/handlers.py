from contextlib import suppress
from datetime import timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.formatting import escape
from bot.export.keyboards import ExportPeriod, export_period_kb, wishes_kb
from bot.export.prompt import build_ai_prompt
from bot.export.service import catalog_exercises, collect_workouts
from bot.export.states import ExportStates
from bot.filters import ExState
from bot.programs.formatters import format_progress, render_program
from bot.programs.parser import PROGRAM_MARKER
from bot.programs.service import get_program
from bot.users.models import User
from bot.users.service import set_ai_wishes
from bot.users.settings import local_now
from bot.workouts.states import WorkoutSession

router = Router(name="export")

# period -> (подпись в файле, глубина в днях; None — вся история)
PERIODS: dict[str, tuple[str, int | None]] = {
    "month": ("last month", 30),
    "6months": ("last 6 months", 182),
    "year": ("last year", 365),
    "all": ("all time", None),
}
MAX_WISHES = 1000
# текст, пока тренировка ждёт ввода, принадлежит ей
WORKOUT_IDLE = StateFilter(None, WorkoutSession.active)
WISHES_PROMPT = (
    "Any requests for the AI? Preferences and limits: full body, "
    "no leg press in my gym, 2.5 kg plates, sore shoulder…\n"
    "Send them as a message, or skip."
)


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    await message.answer(
        "Export workout log as an AI analysis prompt.\nChoose period:",
        reply_markup=export_period_kb(),
    )


@router.callback_query(ExportPeriod.filter())
async def cb_export_period(
    call: CallbackQuery,
    callback_data: ExportPeriod,
    ex_state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    period = PERIODS.get(callback_data.period)
    if period is None:
        await call.answer("Unknown period.", show_alert=True)
        return
    label, _ = period
    # пусто — говорим сразу, а не после вопроса о пожеланиях
    if not await collect_workouts(session, db_user.id, _since(db_user, period)):
        await call.message.edit_text(f"No workouts for {label}.")
        await call.answer()
        return
    await ex_state.set_state(ExportStates.entering_wishes)
    await ex_state.set_data({"period": callback_data.period})
    text = WISHES_PROMPT
    if db_user.ai_wishes:
        text += f"\n\nLast time:\n<i>{escape(db_user.ai_wishes)}</i>"
    await call.message.edit_text(
        text, parse_mode="HTML", reply_markup=wishes_kb(bool(db_user.ai_wishes))
    )
    await call.answer()


@router.message(
    ExState(ExportStates.entering_wishes),
    WORKOUT_IDLE,
    F.text,
    ~F.text.startswith("/"),
)
async def on_wishes(
    message: Message, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    wishes = message.text.strip()
    if len(wishes) > MAX_WISHES:
        await message.answer(
            f"Too long (max {MAX_WISHES} characters). Shorten it and send again."
        )
        return
    await set_ai_wishes(session, db_user, wishes)
    await _send_export(message, ex_state, session, db_user)


@router.callback_query(
    F.data == "exp_wishes_keep", ExState(ExportStates.entering_wishes)
)
async def cb_wishes_keep(
    call: CallbackQuery, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    await _send_export(call.message, ex_state, session, db_user, edit=True)
    await call.answer()


@router.callback_query(
    F.data == "exp_wishes_skip", ExState(ExportStates.entering_wishes)
)
async def cb_wishes_skip(
    call: CallbackQuery, ex_state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    if db_user.ai_wishes is not None:
        await set_ai_wishes(session, db_user, None)
    await _send_export(call.message, ex_state, session, db_user, edit=True)
    await call.answer()


# кнопки пожеланий, когда экспорт уже отдан или сменился другим диалогом
@router.callback_query(F.data.in_({"exp_wishes_keep", "exp_wishes_skip"}))
async def cb_wishes_stale(call: CallbackQuery) -> None:
    await call.answer("This export has expired. Use /export again.", show_alert=True)


@router.callback_query(F.data == "exp_cancel")
async def cb_export_cancel(call: CallbackQuery, ex_state: FSMContext) -> None:
    if await ex_state.get_state() == ExportStates.entering_wishes:
        await ex_state.clear()
    await call.message.edit_text("Export cancelled.")
    await call.answer()


def _since(user: User, period: tuple[str, int | None]):
    _, days = period
    today = local_now(user.utc_offset).date()
    return today - timedelta(days=days) if days is not None else None


async def _send_export(
    message: Message,
    ex_state: FSMContext,
    session: AsyncSession,
    user: User,
    edit: bool = False,
) -> None:
    key = (await ex_state.get_data())["period"]
    await ex_state.clear()
    period = PERIODS[key]
    label, _ = period
    since = _since(user, period)
    today = local_now(user.utc_offset).date()

    async def say(text: str) -> None:
        if edit:
            with suppress(TelegramBadRequest):
                await message.edit_text(text)
        else:
            await message.answer(text)

    workouts = await collect_workouts(session, user.id, since)
    if not workouts:
        # тренировки удалили, пока шёл вопрос о пожеланиях
        await say(f"No workouts for {label}.")
        return
    program = await get_program(session, user.id)
    prompt = build_ai_prompt(
        workouts,
        label,
        since,
        today,
        wishes=user.ai_wishes,
        program_text=render_program(program.days) if program else None,
        program_progress=format_progress(program) if program else None,
        available=await catalog_exercises(session, user.id),
    )
    await say(f"Workout log — {label}.")
    await message.answer_document(
        BufferedInputFile(
            prompt.encode("utf-8"),
            filename=f"workout-log-{key}-{today.isoformat()}.txt",
        ),
        caption=(
            "Send this file to any AI chat. Then paste the AI's "
            f'"{PROGRAM_MARKER}" block back here to load the new program.'
        ),
    )
