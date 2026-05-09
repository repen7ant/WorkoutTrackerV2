from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    result = await session.execute(text("SELECT 1"))
    await message.answer(f"DB ok: {result.scalar()}")


@router.message()
async def any_message(message: Message) -> None:
    await message.answer("I don't understand you")
