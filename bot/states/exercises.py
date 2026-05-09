from aiogram.fsm.state import State, StatesGroup


class ExerciseSearch(StatesGroup):
    waiting_query = State()


class ExerciseAdd(StatesGroup):
    waiting_name = State()
    waiting_muscles = State()
