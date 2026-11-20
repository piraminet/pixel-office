"""Health/readiness + error envelope via httpx ASGI transport (no network).

ASGITransport is async-only (httpx 0.28): all request tests drive AsyncClient
through anyio.run (anyio ships as a FastAPI/starlette dependency).
"""

import anyio
import httpx

from pixel_startup.config import Settings
from pixel_startup.main import create_app


def _app():
    app = create_app(Settings(pixel_api_token="tok-test"))  # type: ignore[call-arg]
    app.state.ready = True
    return app


def test_healthz_public() -> None:
    async def drive() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app()), base_url="http://t"
        ) as c:
            r = await c.get("/healthz")
            assert r.status_code == 200
            assert r.json() == {"status": "ok"}

    anyio.run(drive)


def test_readyz_ready_and_starting() -> None:
    async def drive() -> None:
        app = _app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            assert (await c.get("/readyz")).json() == {"status": "ready"}
            app.state.ready = False
            r = await c.get("/readyz")
            assert r.status_code == 503
            assert r.json()["error"]["code"] == 503

    anyio.run(drive)


def test_error_envelope_on_unknown_route() -> None:
    async def drive() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app()), base_url="http://t"
        ) as c:
            r = await c.get("/api/v1/definitely-not-here")
            assert r.status_code == 404
            assert r.json() == {"error": {"code": 404, "message": "not found"}}

    anyio.run(drive)


def test_ping_unauth_is_401_envelope() -> None:
    async def drive() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_app()), base_url="http://t"
        ) as c:
            r = await c.get("/api/v1/ping")
            assert r.status_code == 401
            assert r.json()["error"] == {"code": 401, "message": "authentication required"}

    anyio.run(drive)
