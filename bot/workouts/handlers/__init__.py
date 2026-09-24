from aiogram import Router

from . import finishing, recording

router = Router(name="workout")
router.include_routers(recording.router, finishing.router)

__all__ = ["router"]
