"""Health/readiness + the first protected /api/v1 route."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from pixel_startup.security.auth import require_auth

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness: public, always 200 (office viewer parity with G2 surface)."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request, response: Response) -> dict:
    if not getattr(request.app.state, "ready", False):
        raise HTTPException(status_code=503, detail="starting")
    response.headers["cache-control"] = "no-store"
    return {"status": "ready"}


@router.get("/api/v1/ping")
async def ping(auth_method: str = Depends(require_auth)) -> dict:
    """First protected route: proves the G2-style auth dependency end to end."""
    return {"pong": True, "auth": auth_method}
