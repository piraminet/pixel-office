"""Auth middleware: bearer + session cookie, fail-closed, synthetic credentials only."""

import anyio
import httpx

from pixel_startup.config import Settings
from pixel_startup.main import create_app
from pixel_startup.security.auth import COOKIE_NAME, create_session_cookie, verify_session_cookie


def _client() -> httpx.AsyncClient:
    app = create_app(Settings(pixel_api_token="tok-test", pixel_session_secret="sectest"))  # type: ignore[call-arg]
    app.state.ready = True
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


def test_bearer_accept_and_reject() -> None:
    async def drive() -> None:
        async with _client() as c:
            r = await c.get("/api/v1/ping", headers={"Authorization": "Bearer tok-test"})
            assert r.status_code == 200
            assert r.json() == {"pong": True, "auth": "bearer"}
            assert (
                await c.get("/api/v1/ping", headers={"Authorization": "Bearer nope"})
            ).status_code == 401
            assert (
                await c.get("/api/v1/ping", headers={"Authorization": "Bearer"})
            ).status_code == 401

    anyio.run(drive)


def test_session_cookie_accept() -> None:
    async def drive() -> None:
        async with _client() as c:
            c.cookies.set(COOKIE_NAME, create_session_cookie("sectest"))
            r = await c.get("/api/v1/ping")
            assert r.status_code == 200
            assert r.json()["auth"] == "session"

    anyio.run(drive)


def test_session_cookie_reject_expired_and_bad_sig() -> None:
    async def drive() -> None:
        async with _client() as c:
            c.cookies.set(
                COOKIE_NAME, create_session_cookie("sectest", ttl_seconds=0, now_ms=1_000_000)
            )
            assert (await c.get("/api/v1/ping")).status_code == 401
            c.cookies.set(COOKIE_NAME, create_session_cookie("other-secret"))
            assert (await c.get("/api/v1/ping")).status_code == 401
            c.cookies.set(COOKIE_NAME, "garbage")
            assert (await c.get("/api/v1/ping")).status_code == 401

    anyio.run(drive)


def test_fail_closed_when_secrets_unset() -> None:
    async def drive() -> None:
        app = create_app(Settings())
        app.state.ready = True
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            assert (await c.get("/api/v1/ping")).status_code == 401

    anyio.run(drive)


def test_cookie_helper_roundtrip() -> None:
    cookie = create_session_cookie("s3", ttl_seconds=60)
    assert verify_session_cookie("s3", cookie)
    assert not verify_session_cookie("s4", cookie)
