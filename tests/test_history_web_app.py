import asyncio
import logging

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

from history_web.app import QuietHealthAccessLogger, create_app


# без базы: до сессии запрос не доходит
def test_api_requires_valid_init_data():
    async def run():
        app = create_app("123456:TEST", sessionmaker=None)
        async with TestClient(TestServer(app)) as client:
            assert (await client.get("/api/workouts")).status == 401
            bad = {"Authorization": "tma garbage"}
            assert (await client.get("/api/workouts", headers=bad)).status == 401

    asyncio.run(run())


def test_health_without_auth_and_db():
    async def run():
        app = create_app("123456:TEST", sessionmaker=None)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/health")
            assert resp.status == 200
            assert await resp.json() == {"status": "ok"}

    asyncio.run(run())


def test_access_log_skips_health(caplog):
    access = QuietHealthAccessLogger(logging.getLogger("test.access"))
    with caplog.at_level(logging.INFO, logger="test.access"):
        access.log(make_mocked_request("GET", "/health"), web.Response(), 0.01)
        assert caplog.records == []
        access.log(make_mocked_request("GET", "/"), web.Response(), 0.01)
        assert '"GET / HTTP/1.1" 200' in caplog.text
