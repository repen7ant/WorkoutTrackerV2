from aiogram import Router

from . import exercises, history, start, workout


def get_routers() -> list[Router]:
    return [
        exercises.router,
        workout.router,
        history.router,
        start.router,
    ]
