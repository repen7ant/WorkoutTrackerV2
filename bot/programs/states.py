from aiogram.fsm.state import State, StatesGroup


class ProgramImport(StatesGroup):
    """Мастер импорта — на дорожке диалогов упражнений (ex_state)."""

    matching = State()  # упражнение плана не найдено в каталоге
    entering_muscles = State()  # создаём его — ввод мышц
    confirming = State()  # сводка перед сохранением
