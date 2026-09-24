from aiogram import Router

from bot.catalog import handlers as catalog
from bot.export import handlers as export
from bot.history import handlers as history
from bot.workouts import handlers as workouts

from . import start


def get_routers() -> list[Router]:
    return [
        catalog.router,
        workouts.router,
        history.router,
        export.router,
        # последним: в нём ловушка для любых сообщений
        start.router,
    ]
