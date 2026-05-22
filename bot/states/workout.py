from aiogram.fsm.state import State, StatesGroup


class WorkoutSession(StatesGroup):
    active = State()           # тренировка идёт, ждём кнопок
    choosing_exercise = State()  # ввод названия упражнения
    entering_sets = State()    # ввод подходов
    finishing = State()        # выбор даты
    entering_date = State()
    entering_notes = State()
    confirming = State()       # проверка даты и заметки перед сохранением
