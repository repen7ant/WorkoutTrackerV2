from aiogram import Router

from . import exercises, start


def get_routers() -> list[Router]:
    return [
        exercises.router,
        start.router,
    ]
