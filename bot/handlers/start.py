from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "/exercises — exercises interaction\n/sessions — workout sessions history\n/workout — start workout session"
    )


@router.message()
async def any_message(message: Message) -> None:
    await message.answer("use /start to see all available commands")
