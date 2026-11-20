"""Application factory: lifecycle, error envelope, DI seam, structured logging.

G4 criteria covered here:
- main.py lifecycle: startup, readiness flag, graceful shutdown handler.
- Consistent error envelope on every error path: {"error": {"code", "message"}}.
  Secrets/internals are never echoed (500s are opaque).
- Dependency injection seam: app.state.container (provider registry lands in G5).
- Docs endpoints disabled for the candidate backend (G2 hardening parity).
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pixel_startup.api import health
from pixel_startup.config import Settings, load_settings
from pixel_startup.log import logger, setup_logging
from pixel_startup.persistence.db import Database
from pixel_startup.persistence.store import (
    ApprovalStore,
    AuditStore,
    EmployeeStore,
    OfficePersistenceProvider,
    TaskStore,
)
from pixel_startup.providers.registry import (
    ProviderCategory,
    ProviderRegistration,
    ProviderRegistry,
    ProviderState,
)


@dataclass
class Container:
    """Dependency-injection seam; the G5 provider registry lives here."""

    providers: dict[str, object] = field(default_factory=dict)
    registry: ProviderRegistry = field(default_factory=ProviderRegistry)
    shutdowns: int = 0

    def register(self, provider_id: str, provider: object) -> None:
        self.providers[provider_id] = provider


def _register_deployed_js_stack(container: Container, settings: Settings) -> None:
    """The deployed JS implementation enters the registry top-priority and ACTIVE.

    Mandate G5: the currently deployed implementation retains priority until its
    replacement is qualified — modeled as an explicit promotion sequence, not a
    registration shortcut.
    """
    reg = container.registry.register(
        ProviderRegistration(
            provider_id="pixel_office_js",
            category=ProviderCategory.OPERATIONAL_PERSISTENCE,
            implementation="javascript",
            endpoint=f"http://127.0.0.1:{settings.port}",
            capabilities=["agents.config.read", "rooms.read", "actions.append"],
            priority=100,
            detail="deployed JS stack: authoritative until Python qualifies",
        )
    )
    container.registry.transition(reg.provider_id, ProviderState.CANDIDATE)
    container.registry.transition(reg.provider_id, ProviderState.QUALIFIED)
    container.registry.transition(reg.provider_id, ProviderState.ACTIVE)


def _register_python_persistence(container: Container, settings: Settings) -> None:
    """G6: open the operational store, migrate, and register as a QUALIFIED provider.

    Deliberately NOT activated — the deployed JS stack stays the active
    persistence provider until cutover (G20)."""
    import os

    db = Database(os.path.join(settings.pixel_data_dir, "pixel_startup.sqlite3"))
    version = db.migrate()
    handler = OfficePersistenceProvider(db)
    container.providers["db"] = db
    container.providers["employees"] = EmployeeStore(db)
    container.providers["tasks"] = TaskStore(db)
    container.providers["approvals"] = ApprovalStore(db)
    container.providers["audit"] = AuditStore(db)
    container.registry.register(
        ProviderRegistration(
            provider_id="pixel_startup_sqlite",
            category=ProviderCategory.OPERATIONAL_PERSISTENCE,
            implementation="python",
            handler=handler,
            endpoint=None,
            capabilities=["persistence.health.counts", "employees.upsert", "tasks.lifecycle"],
            priority=10,
            detail=f"candidate ops store (schema v{version}); activation deferred to G20",
        )
    )
    container.registry.transition("pixel_startup_sqlite", ProviderState.CANDIDATE)
    container.registry.transition("pixel_startup_sqlite", ProviderState.QUALIFIED)


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
    _register_deployed_js_stack(container, settings)
    _register_python_persistence(container, settings)
    logger.info(
        "backend starting",
        extra={
            "event": "startup",
            "component": "pixel_startup",
            "detail": (
                f"secrets: session_secret={'set' if settings.is_session_secret_set else 'UNSET'}, "
                f"api_token={'set' if settings.is_api_token_set else 'UNSET'}; "
                f"providers={len(container.registry.all())}"
            ),
        },
    )
    active_count = sum(1 for p in container.registry.all() if p.state is ProviderState.ACTIVE)
    logger.info(
        "provider snapshot",
        extra={
            "event": "providers.snapshot",
            "component": "registry",
            "detail": f"active={active_count}",
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
