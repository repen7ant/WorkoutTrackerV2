from contextlib import suppress

import structlog
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent, Message
from structlog.typing import FilteringBoundLogger

logger: FilteringBoundLogger = structlog.get_logger()

USER_MESSAGE = "Something went wrong. Nothing is lost — try again."


def _reply_target(event: ErrorEvent) -> Message | None:
    update = event.update
    if update.message is not None:
        return update.message
    if update.callback_query is not None:
        return update.callback_query.message
    return None


async def on_error(event: ErrorEvent) -> bool:
    """
    Последний рубеж: без него любое исключение в хендлере оборачивалось для
    пользователя молчанием — бот просто переставал отвечать.
    """
    await logger.aexception(
        "Unhandled error while processing update",
        update_id=event.update.update_id,
        error=repr(event.exception),
    )

    # спиннер на кнопке висит до ответа на callback — гасим его в любом случае
    if event.update.callback_query is not None:
        with suppress(TelegramAPIError):
            await event.update.callback_query.answer()

    target = _reply_target(event)
    if target is not None:
        try:
            await target.answer(USER_MESSAGE)
        except TelegramAPIError:
            await logger.awarning("Could not deliver error message to user")

    return True
