"""Environment-driven settings for the DataSentinel backend."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

INSECURE_DEFAULT_SECRET_KEY = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DATASENTINEL_",
        case_sensitive=False,
        extra="ignore",
    )

    env: str = "development"

    database_url: str = "postgresql+psycopg://datasentinel:datasentinel@localhost:5432/datasentinel"

    secret_key: str = Field(default=INSECURE_DEFAULT_SECRET_KEY)
    access_token_expire_minutes: int = 30

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @model_validator(mode="after")
    def _refuse_insecure_secret_in_production(self) -> "Settings":
        # Fail loud at settings-construction time (before the app, a CLI
        # script, or an Alembic migration ever runs) rather than silently
        # signing JWTs with a publicly-known key in production.
        if self.is_production and self.secret_key == INSECURE_DEFAULT_SECRET_KEY:
            raise ValueError(
                "DATASENTINEL_SECRET_KEY must be set to a real secret when DATASENTINEL_ENV=production "
                "(refusing to start with the insecure default — generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
