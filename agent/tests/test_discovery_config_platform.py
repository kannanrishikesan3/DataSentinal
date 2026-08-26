"""Phase 2 (macOS support): discovery/config.py's `_current_os_key()` now
goes through the shared 3-way `detect_platform()` instead of a binary
windows/linux ternary that would have misreported macOS as Linux."""

from datasentinel_agent.discovery.config import _current_os_key, resolve_default_include_paths
from datasentinel_agent.config.scan_config import load_scan_config


def test_current_os_key_resolves_macos(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert _current_os_key() == "macos"


def test_current_os_key_resolves_windows(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    assert _current_os_key() == "windows"


def test_current_os_key_resolves_linux(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert _current_os_key() == "linux"


def test_macos_include_paths_are_empty_until_phase_3_adds_them(monkeypatch):
    # config/default.yaml has no `macos:` section yet (that's Phase 3's
    # scope) — resolving on a detected Mac must degrade to an empty list,
    # never raise, since `ScanConfig.include_paths` is a plain dict.
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert resolve_default_include_paths(load_scan_config()) == []
