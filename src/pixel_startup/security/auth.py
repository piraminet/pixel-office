"""Authentication mirroring the G2 model: signed session cookie OR bearer token.

Fail-closed semantics:
- Bearer accepted only when it byte-matches PIXEL_API_TOKEN (unset => always 401).
- Session cookies accepted only when verifiable against PIXEL_SESSION_SECRET
  (unset => always 401), including an expiry check.
The candidate cookie format (`v1.<expiry_ms>.<hmac-sha256-hex>`) is NOT yet
wire-compatible with the JS backend's cookie; parity is a G20 concern.
"""

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request

from pixel_startup.config import Settings

COOKIE_NAME = "pixel_session"
_AUTH_REQUIRED = HTTPException(status_code=401, detail="authentication required")


def create_session_cookie(secret: str, ttl_seconds: int = 43200, now_ms: int | None = None) -> str:
    """Issue a signed, self-expiring session cookie value."""
    expiry = (now_ms if now_ms is not None else int(time.time() * 1000)) + ttl_seconds * 1000
    message = f"v1.{expiry}".encode()
    sig = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"v1.{expiry}.{sig}"


def verify_session_cookie(secret: str, cookie: str, now_ms: int | None = None) -> bool:
    parts = cookie.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        return False
    expiry_raw, sig = parts[1], parts[2]
    if not expiry_raw.isdigit():
        return False
    expected = hmac.new(secret.encode(), f"v1.{expiry_raw}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False
    if int(expiry_raw) < (now_ms if now_ms is not None else int(time.time() * 1000)):
        return False
    return True


def require_auth(request: Request) -> str:
    """FastAPI dependency: returns the auth method or raises 401 (fail closed)."""
    settings: Settings = request.app.state.settings
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer ") and settings.is_api_token_set:
        token = header[len("Bearer ") :]
        if token and secrets.compare_digest(token, settings.pixel_api_token or ""):
            return "bearer"
    cookie = request.cookies.get(COOKIE_NAME, "")
    if cookie and settings.is_session_secret_set:
        if verify_session_cookie(settings.pixel_session_secret or "", cookie):
            return "session"
    raise _AUTH_REQUIRED
