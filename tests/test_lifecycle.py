"""Lifecycle: startup/readiness/graceful shutdown exercised through the lifespan."""

import httpx

from pixel_startup.config import Settings
from pixel_startup.main import create_app


def test_lifespan_startup_and_graceful_shutdown() -> None:
    app = create_app(Settings())
    container = app.state.container
    assert container.shutdowns == 0
    assert app.state.ready is False

    async def drive() -> None:
        async with app.router.lifespan_context(app):
            assert app.state.ready is True
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                assert (await c.get("/readyz")).status_code == 200

    import anyio

    anyio.run(drive)
    assert app.state.ready is False
    assert container.shutdowns == 1


def test_container_di_seam() -> None:
    app = create_app(Settings())
    container = app.state.container
    container.register("probe", object())
    assert "probe" in container.providers
