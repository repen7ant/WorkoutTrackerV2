from dataclasses import replace
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import TelegramObject

EXERCISES_DESTINY = "exercises"


class SubFSMMiddleware(BaseMiddleware):
    """
    Заводит вторую FSM-дорожку поверх той, что уже собрал aiogram.

    Дорожки различаются полем destiny в StorageKey, поэтому диалоги упражнений
    (ex_state) не трогают состояние и данные активной тренировки (state).
    """

    def __init__(self, destiny: str, state_key: str = "ex_state"):
        self.destiny = destiny
        self.state_key = state_key
        self.raw_state_key = f"{state_key.removesuffix('state')}raw_state"

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state: FSMContext | None = data.get("state")
        storage: BaseStorage | None = data.get("fsm_storage")
        if state is None or storage is None:
            return await handler(event, data)

        sub_state = FSMContext(
            storage=storage,
            key=replace(state.key, destiny=self.destiny),
        )
        data[self.state_key] = sub_state
        data[self.raw_state_key] = await sub_state.get_state()
        return await handler(event, data)
