"""
Все модели разом — только для Alembic, которому нужна полная метадата.

Код модулей импортирует модели своего модуля напрямую и чужие таблицы не трогает.
"""

from bot.catalog.models import Exercise, ExerciseMuscle, Muscle
from bot.db.base import Base
from bot.users.models import User
from bot.workouts.models import Set, Workout, WorkoutExercise

__all__ = [
    "Base",
    "Exercise",
    "ExerciseMuscle",
    "Muscle",
    "Set",
    "User",
    "Workout",
    "WorkoutExercise",
]
