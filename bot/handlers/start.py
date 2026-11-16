from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")

START_TEXT = (
    "Log your workouts and let an AI coach plan the next ones.\n"
    "\n"
    "How it works:\n"
    "1. /workout — log your training for a while.\n"
    "2. /export — get your log as a file with a prompt for an AI.\n"
    "3. Send the file to any AI chat and read its analysis.\n"
    "4. Paste the AI's block that starts with # PROGRAM back here.\n"
    "5. Now /workout offers the next day of the plan: just tick off the sets. "
    "The days repeat in a loop — the program has no end.\n"
    "6. After a few weeks, /export again: the AI sees the plan and what you "
    "actually did and gives you the next program. Paste it — it replaces "
    "the old one.\n"
    "\n"
    "/workout — start workout session\n"
    "/history — workout sessions history\n"
    "/exercises — exercises interaction\n"
    "/export — export log as an AI analysis prompt\n"
    "/program — current program\n"
    "/settings — workout preferences"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message()
async def any_message(message: Message) -> None:
    await message.answer("use /start to see all available commands")
