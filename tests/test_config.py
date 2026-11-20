"""Config loading from environment; no secret defaults."""

import importlib

import pytest

from pixel_startup.config import Settings, load_settings


def test_defaults_have_no_secrets() -> None:
    s = Settings()
    assert s.pixel_api_token is None
    assert s.pixel_session_secret is None
    assert s.dashboard_password is None
    assert s.port == 19000


def test_env_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIXEL_API_TOKEN", "tok-abc")
    monkeypatch.setenv("PIXEL_SESSION_SECRET", "sectest")
    s = load_settings()
    assert s.pixel_api_token == "tok-abc"
    assert s.is_api_token_set
    assert s.is_session_secret_set


def test_load_helper_is_the_documented_entrypoint() -> None:
    module = importlib.import_module("pixel_startup.main")
    assert module is not None
