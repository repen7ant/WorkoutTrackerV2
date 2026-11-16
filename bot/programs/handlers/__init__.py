from aiogram import Router

from . import import_

router = Router(name="programs")
router.include_routers(import_.router)

__all__ = ["router"]
