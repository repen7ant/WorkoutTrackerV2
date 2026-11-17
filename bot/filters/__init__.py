from aiogram.filters import StateFilter

from bot.filters.ex_state import ExState
from bot.workouts.states import WorkoutSession

# Текст, пока тренировка ждёт ввода, принадлежит ей: диалоги на дорожке
# ex_state читают сообщения только вне ввода. В WorkoutSession.active
# тренировка управляется кнопками, текст ей не нужен.
WORKOUT_IDLE = StateFilter(None, WorkoutSession.active)

__all__ = ["WORKOUT_IDLE", "ExState"]
