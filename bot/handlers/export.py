from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.export import ExportPeriod, export_period_kb
from bot.models.users import User
from bot.repositories.workout import WorkoutRepository
from bot.utils.formatters import build_ai_prompt

router = Router(name="export")

# period -> (подпись в файле, глубина в днях; None — вся история)
PERIODS: dict[str, tuple[str, int | None]] = {
    "month": ("last month", 30),
    "6months": ("last 6 months", 182),
    "year": ("last year", 365),
    "all": ("all time", None),
}


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
    session: AsyncSession,
    db_user: User,
) -> None:
    period = PERIODS.get(callback_data.period)
    if period is None:
        await call.answer("Unknown period.", show_alert=True)
        return
    label, days = period

    today = date.today()
    since = today - timedelta(days=days) if days is not None else None

    repo = WorkoutRepository(session)
    workouts = await repo.get_workouts_for_export(db_user.id, since)
    if not workouts:
        await call.message.edit_text(f"No workouts for {label}.")
        await call.answer()
        return

    prompt = build_ai_prompt(workouts, label, since, today)
    filename = f"workout-log-{callback_data.period}-{today.isoformat()}.txt"

    await call.message.edit_text(f"Workout log — {label}.")
    await call.message.answer_document(
        BufferedInputFile(prompt.encode("utf-8"), filename=filename),
        caption="Send this file to any AI chat to get a progress analysis.",
    )
    await call.answer()


@router.callback_query(F.data == "exp_cancel")
async def cb_export_cancel(call: CallbackQuery) -> None:
    await call.message.edit_text("Export cancelled.")
    await call.answer()
