"""Phase 1 smoke tests: backend settings load with safe defaults."""

import pytest

from datasentinel_backend.core.config import Settings


def test_defaults_are_development_and_local_db(monkeypatch):
    for var in ("DATASENTINEL_ENV", "DATASENTINEL_DATABASE_URL", "DATASENTINEL_CORS_ORIGINS"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.env == "development"
    assert settings.is_production is False
    assert "localhost" in settings.database_url


def test_cors_origins_parsed_from_comma_separated_string(monkeypatch):
    monkeypatch.setenv("DATASENTINEL_CORS_ORIGINS", "https://a.example.com, https://b.example.com")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_refuses_insecure_default_secret_in_production(monkeypatch):
    monkeypatch.setenv("DATASENTINEL_ENV", "production")
    monkeypatch.delenv("DATASENTINEL_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="insecure default"):
        Settings(_env_file=None)


def test_production_with_a_real_secret_key_is_fine(monkeypatch):
    monkeypatch.setenv("DATASENTINEL_ENV", "production")
    monkeypatch.setenv("DATASENTINEL_SECRET_KEY", "a-real-randomly-generated-secret")
    settings = Settings(_env_file=None)
    assert settings.is_production is True
