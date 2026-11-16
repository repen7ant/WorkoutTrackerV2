from aiogram.fsm.state import State, StatesGroup


class ExportStates(StatesGroup):
    """На дорожке диалогов (ex_state): экспорт можно делать посреди тренировки."""

    entering_wishes = State()
