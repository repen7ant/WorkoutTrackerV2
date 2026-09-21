from typing import Any

from aiogram.filters import StateFilter
from aiogram.types import TelegramObject


class ExState(StateFilter):
    """
    То же, что StateFilter, но смотрит на дорожку диалогов упражнений.

    Штатный StateFilter читает raw_state — состояние дефолтной дорожки, где
    живёт тренировка. Эта версия читает ex_raw_state, который кладёт
    SubFSMMiddleware.
    """

    async def __call__(  # type: ignore[override]
        self,
        obj: TelegramObject,
        ex_raw_state: str | None = None,
    ) -> bool | dict[str, Any]:
        return await super().__call__(obj, raw_state=ex_raw_state)
