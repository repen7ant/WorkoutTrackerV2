from aiogram import Router

from . import import_, view

router = Router(name="programs")
router.include_routers(view.router, import_.router)

__all__ = ["router"]
