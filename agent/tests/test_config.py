"""Phase 1 smoke tests: configuration loads correctly and is safe by default."""

import importlib

from datasentinel_agent.config.settings import Settings
from datasentinel_agent.config.scan_config import load_scan_config


def test_env_file_defaults_to_relative_dotenv(monkeypatch):
    monkeypatch.delenv("DATASENTINEL_ENV_FILE", raising=False)
    import datasentinel_agent.config.settings as settings_module

    importlib.reload(settings_module)
    try:
        assert settings_module.Settings.model_config["env_file"] == ".env"
    finally:
        importlib.reload(settings_module)  # restore real env for later tests


def test_env_file_override_is_honored_for_service_contexts_with_unknown_cwd(monkeypatch, tmp_path):
    """A Windows Service (or a systemd unit with its own WorkingDirectory)
    isn't guaranteed to run with CWD == the install directory, so a plain
    relative ".env" could silently miss the file `datasentinel enroll`
    wrote. DATASENTINEL_ENV_FILE lets an installer pin an absolute path."""
    pinned = tmp_path / "agent.env"
    pinned.write_text("DATASENTINEL_ENDPOINT_TOKEN=from-pinned-file\n", encoding="utf-8")
    monkeypatch.setenv("DATASENTINEL_ENV_FILE", str(pinned))

    import datasentinel_agent.config.settings as settings_module

    importlib.reload(settings_module)
    try:
        assert settings_module.Settings.model_config["env_file"] == str(pinned)
        assert settings_module.Settings().endpoint_token == "from-pinned-file"
    finally:
        monkeypatch.delenv("DATASENTINEL_ENV_FILE", raising=False)
        importlib.reload(settings_module)


def test_settings_defaults_to_ai_disabled(monkeypatch):
    monkeypatch.delenv("AI_ENABLED", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.ai_enabled is False
    assert settings.ai_configured is False


def test_settings_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_MODEL", "test-model")
    settings = Settings(_env_file=None)
    assert settings.ai_enabled is True
    assert settings.ai_configured is True


def test_scan_config_loads_default_yaml():
    config = load_scan_config()
    assert config.scan.default_profile == "standard"
    assert {"quick", "standard", "deep", "custom"} <= set(config.scan.profiles)
    assert "/proc" in config.exclude_paths["linux"]
    assert ".pdf" in config.supported_extensions


def test_scan_config_max_memory_mb_round_trips_from_default_yaml():
    config = load_scan_config()
    assert config.scan.max_memory_mb == 2048
    assert isinstance(config.scan.max_memory_mb, int)


def test_scan_config_archive_limits_round_trip_from_default_yaml():
    config = load_scan_config()
    assert config.archive_limits.max_members == 10_000
    assert config.archive_limits.max_uncompressed_bytes == 500 * 1024 * 1024
    assert config.archive_limits.max_ratio == 200


def test_scan_config_profile_lookup():
    config = load_scan_config()
    quick = config.profile("quick")
    assert quick.max_file_size_mb == 5

    import pytest

    with pytest.raises(ValueError):
        config.profile("does-not-exist")


def test_load_scan_config_explicit_path_wins_over_everything(tmp_path, monkeypatch):
    override = tmp_path / "explicit.yaml"
    override.write_text("scan:\n  default_profile: quick\n  profiles:\n    quick:\n      max_file_size_mb: 1\n      max_depth: 1\n      worker_limit: 1\n")
    monkeypatch.setenv("DATASENTINEL_SCAN_CONFIG_PATH", str(tmp_path / "unused.yaml"))

    config = load_scan_config(override)
    assert config.scan.default_profile == "quick"
    assert config.scan.profiles["quick"].max_file_size_mb == 1


def test_load_scan_config_env_override_used_when_no_explicit_path(tmp_path, monkeypatch):
    override = tmp_path / "from-env.yaml"
    override.write_text("scan:\n  default_profile: deep\n  profiles:\n    deep:\n      max_file_size_mb: 2\n      max_depth: 2\n      worker_limit: 2\n")
    monkeypatch.setenv("DATASENTINEL_SCAN_CONFIG_PATH", str(override))

    config = load_scan_config()
    assert config.scan.default_profile == "deep"
    assert config.scan.profiles["deep"].max_file_size_mb == 2


def test_load_scan_config_falls_back_to_bundled_default_without_env_override(monkeypatch):
    monkeypatch.delenv("DATASENTINEL_SCAN_CONFIG_PATH", raising=False)
    config = load_scan_config()
    assert config.scan.default_profile == "standard"
