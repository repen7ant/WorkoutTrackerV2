from aiogram import Router

from . import exercises, start, workout


def get_routers() -> list[Router]:
    return [
        exercises.router,
        workout.router,
        start.router,
    ]
