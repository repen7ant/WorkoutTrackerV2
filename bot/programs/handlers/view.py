from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.formatting import escape
from bot.common.keyboards import yes_no_kb
from bot.programs.formatters import render_program
from bot.programs.keyboards import program_kb
from bot.programs.service import delete_program, get_program
from bot.users.models import User

router = Router(name="program_view")

NO_PROGRAM = (
    "No program yet.\n"
    "1. /export your log and send the file to any AI chat.\n"
    "2. Paste the AI's block that starts with # PROGRAM back here."
)
# сообщение Telegram — не длиннее 4096 символов, с тегами <pre>
MAX_MESSAGE_LENGTH = 4000


@router.message(Command("program"))
async def cmd_program(message: Message, session: AsyncSession, db_user: User) -> None:
    program = await get_program(session, db_user.id)
    if program is None:
        await message.answer(NO_PROGRAM)
        return
    text = render_program(program.days)
    if len(escape(text)) > MAX_MESSAGE_LENGTH:
        await message.answer_document(
            BufferedInputFile(text.encode("utf-8"), filename="program.txt"),
            caption="Your program.",
            reply_markup=program_kb(),
        )
        return
    await message.answer(
        f"<pre>{escape(text)}</pre>", parse_mode="HTML", reply_markup=program_kb()
    )


# вопрос — новым сообщением: программа могла прийти файлом, у него нет текста
@router.callback_query(F.data == "pg_delete")
async def cb_delete(call: CallbackQuery) -> None:
    await call.message.answer(
        "Delete program? Workouts you've logged stay.",
        reply_markup=yes_no_kb("pg_delete_yes", "pg_delete_no"),
    )
    await call.answer()


@router.callback_query(F.data == "pg_delete_yes")
async def cb_delete_yes(
    call: CallbackQuery, session: AsyncSession, db_user: User
) -> None:
    try:
        # снимаем сразу: второй тап иначе ответил бы «No program»
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        await call.answer()
        return
    deleted = await delete_program(session, db_user.id)
    await call.message.edit_text("Program deleted." if deleted else "No program.")
    await call.answer()


@router.callback_query(F.data == "pg_delete_no")
async def cb_delete_no(call: CallbackQuery) -> None:
    await call.message.delete()
    await call.answer()
