"""Environment-driven settings for the DataSentinel agent.

Secrets and per-install values (API keys, backend URL, DB path) come from the
environment / `.env` file. Operational scan defaults (profiles, include/exclude
paths) live in `scan_config.py` / `agent/config/default.yaml` instead, since those
are meant to be reviewed and version-controlled, not treated as secrets.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Relative ".env" resolves against the process's current working directory,
# which is fine for the CLI (always run from a chosen directory) but not
# guaranteed for a Windows Service launched by the SCM, or a systemd unit
# with its own WorkingDirectory — neither is guaranteed to match wherever
# `datasentinel enroll` wrote credentials. DATASENTINEL_ENV_FILE lets an
# installer pin an absolute path once (as a machine/service environment
# variable) so the same env file is found regardless of process CWD; unset,
# behavior is unchanged (relative ".env", resolved from CWD as before).
_ENV_FILE = os.environ.get("DATASENTINEL_ENV_FILE", ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AI (optional — the scanner must work fully with this disabled)
    ai_enabled: bool = Field(default=False, alias="AI_ENABLED")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model: str | None = Field(default=None, alias="OPENROUTER_MODEL")

    # Backend connection (optional — the agent can run fully offline)
    backend_url: str | None = Field(default=None, alias="DATASENTINEL_BACKEND_URL")
    endpoint_token: str | None = Field(default=None, alias="DATASENTINEL_ENDPOINT_TOKEN")

    # Local storage
    db_path: str = Field(default="./datasentinel.db", alias="DATASENTINEL_DB_PATH")

    # Logging
    log_level: str = Field(default="INFO", alias="DATASENTINEL_LOG_LEVEL")

    @property
    def ai_configured(self) -> bool:
        """AI is only actually usable if enabled AND an API key/model are present."""
        return bool(self.ai_enabled and self.openrouter_api_key and self.openrouter_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
