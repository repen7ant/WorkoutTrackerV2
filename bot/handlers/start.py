from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer("Hello")


@router.message()
async def any_message(message: Message) -> None:
    await message.answer("I don't understand you")
