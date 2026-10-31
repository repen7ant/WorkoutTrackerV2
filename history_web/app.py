from datetime import UTC, datetime
from pathlib import Path

from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.workouts.repository import WorkoutRepository
from history_web.auth import Unauthorized, user_id_from_init_data
from history_web.progress import build_progress
from history_web.schemas import (
    progress_to_json,
    workout_summary_to_json,
    workout_to_json,
)

STATIC_DIR = Path(__file__).parent / "static"
PER_PAGE = 20

token_key = web.AppKey("token", str)
sessionmaker_key = web.AppKey("sessionmaker", async_sessionmaker)

routes = web.RouteTableDef()


def error(status: int, message: str) -> web.Response:
    return web.json_response({"error": message}, status=status)


@web.middleware
async def api_middleware(request: web.Request, handler) -> web.StreamResponse:
    """Для /api/*: пользователь из initData и сессия БД на запрос."""
    if not request.path.startswith("/api/"):
        return await handler(request)

    scheme, _, init_data = request.headers.get("Authorization", "").partition(" ")
    if scheme != "tma":
        return error(401, "unauthorized")
    try:
        request["user_id"] = user_id_from_init_data(
            request.app[token_key], init_data, now=datetime.now(UTC)
        )
    except Unauthorized:
        return error(401, "unauthorized")

    async with request.app[sessionmaker_key]() as session:
        request["session"] = session
        return await handler(request)


@routes.get("/")
async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


@routes.get("/api/workouts")
async def list_workouts(request: web.Request) -> web.Response:
    page = request.query.get("page", "1")
    if not page.isdigit() or int(page) < 1:
        return error(400, "page must be a positive integer")
    workouts, total_pages = await WorkoutRepository(request["session"]).page(
        request["user_id"], int(page), per_page=PER_PAGE
    )
    return web.json_response(
        {
            "items": [workout_summary_to_json(w) for w in workouts],
            "page": int(page),
            "total_pages": total_pages,
        }
    )


@routes.get(r"/api/workouts/{id:\d+}")
async def get_workout(request: web.Request) -> web.Response:
    workout = await WorkoutRepository(request["session"]).get(
        int(request.match_info["id"]), request["user_id"]
    )
    if workout is None:
        return error(404, "not found")
    return web.json_response(workout_to_json(workout))


@routes.get("/api/exercises")
async def list_exercises(request: web.Request) -> web.Response:
    exercises = await WorkoutRepository(request["session"]).logged_exercises(
        request["user_id"]
    )
    return web.json_response([{"id": ex.id, "name": ex.name} for ex in exercises])


@routes.get(r"/api/exercises/{id:\d+}/progress")
async def exercise_progress(request: web.Request) -> web.Response:
    workouts = await WorkoutRepository(request["session"]).with_exercise(
        int(request.match_info["id"]), request["user_id"], limit=None
    )
    return web.json_response(progress_to_json(build_progress(workouts)))


def create_app(
    token: str, sessionmaker: async_sessionmaker[AsyncSession]
) -> web.Application:
    app = web.Application(middlewares=[api_middleware])
    app[token_key] = token
    app[sessionmaker_key] = sessionmaker
    app.add_routes(routes)
    app.router.add_static("/static/", STATIC_DIR)
    return app
