from aiogram import Router

from . import exercises, export, history, start, workout


def get_routers() -> list[Router]:
    return [
        exercises.router,
        workout.router,
        history.router,
        export.router,
        start.router,
    ]
