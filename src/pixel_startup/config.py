"""Typed configuration from environment (pydantic-settings).

Principle 5/G10: no secret values have defaults; secrets are loaded from the
environment only and are never logged. Presence flags (is_*_set) exist so that
logging and diagnostics can report capability without touching the value.
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    port: int = 19000
    # Operational
    pixel_data_dir: str = "./data"
    # Secrets (no defaults — fail closed when unset)
    pixel_session_secret: str | None = None
    pixel_api_token: str | None = None
    dashboard_password: str | None = None
    pixel_allow_no_password: bool = False

    @property
    def is_session_secret_set(self) -> bool:
        return bool(self.pixel_session_secret)

    @property
    def is_api_token_set(self) -> bool:
        return bool(self.pixel_api_token)

    @classmethod
    def load(cls) -> "Settings":
        return cls()


def load_settings() -> Settings:
    """Load Settings from the process environment (helper for tests + main)."""
    return Settings(_env_file=os.environ.get("PIXEL_STARTUP_ENV_FILE", None))  # type: ignore[call-arg]
