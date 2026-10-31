import asyncio

from aiohttp.test_utils import TestClient, TestServer

from history_web.app import create_app


# без базы: до сессии запрос не доходит
def test_api_requires_valid_init_data():
    async def run():
        app = create_app("123456:TEST", sessionmaker=None)
        async with TestClient(TestServer(app)) as client:
            assert (await client.get("/api/workouts")).status == 401
            bad = {"Authorization": "tma garbage"}
            assert (await client.get("/api/workouts", headers=bad)).status == 401

    asyncio.run(run())
