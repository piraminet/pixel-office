"""Application factory: lifecycle, error envelope, DI seam, structured logging.

G4 criteria covered here:
- main.py lifecycle: startup, readiness flag, graceful shutdown handler.
- Consistent error envelope on every error path: {"error": {"code", "message"}}.
  Secrets/internals are never echoed (500s are opaque).
- Dependency injection seam: app.state.container (provider registry lands in G5).
- Docs endpoints disabled for the candidate backend (G2 hardening parity).
"""

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pixel_startup.api import health
from pixel_startup.config import Settings, load_settings
from pixel_startup.log import setup_logging

logger = logging.getLogger("pixel_startup.main")


@dataclass
class Container:
    """Dependency-injection seam. Providers register here starting with G5."""

    providers: dict[str, object] = field(default_factory=dict)
    shutdowns: int = 0

    def register(self, provider_id: str, provider: object) -> None:
        self.providers[provider_id] = provider


def build_error(status_code: int, message: str, detail: str | None = None) -> JSONResponse:
    body: dict = {"error": {"code": status_code, "message": message}}
    if detail:
        body["error"]["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    container: Container = app.state.container
    setup_logging()
    logger.info(
        "backend starting",
        extra={
            "event": "startup",
            "component": "pixel_startup",
            "detail": (
                f"secrets: session_secret={'set' if settings.is_session_secret_set else 'UNSET'}, "
                f"api_token={'set' if settings.is_api_token_set else 'UNSET'}; "
                f"providers={len(container.providers)}"
            ),
        },
    )
    app.state.ready = True
    try:
        yield
    finally:
        app.state.ready = False
        container.shutdowns += 1
        logger.info(
            "backend stopped gracefully", extra={"event": "shutdown", "component": "pixel_startup"}
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        title="Pixel Startup backend",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings if settings is not None else load_settings()
    app.state.container = Container()
    app.state.ready = False
    app.include_router(health.router)

    @app.exception_handler(HTTPException)
    async def _http_exc(_: Request, exc: HTTPException) -> JSONResponse:
        return build_error(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # locations + messages only; input values are never echoed back.
        detail = "; ".join(
            f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg', 'invalid')}"
            for err in exc.errors()
        )
        return build_error(422, "validation failed", detail)

    @app.exception_handler(404)
    async def _not_found(_: Request, exc: HTTPException) -> JSONResponse:
        return build_error(404, "not found")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, __: Exception) -> JSONResponse:
        return build_error(500, "internal error")

    return app


app = create_app()
