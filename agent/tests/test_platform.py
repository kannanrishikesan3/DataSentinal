"""Phase 2 (macOS support): the shared 3-way platform detector that
replaced the old binary windows/linux ternaries in discovery/config.py and
cli/main.py's enroll()."""

from datasentinel_agent.core.platform import Platform, detect_platform


def test_detect_platform_windows(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    assert detect_platform() == Platform.WINDOWS


def test_detect_platform_macos(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert detect_platform() == Platform.MACOS


def test_detect_platform_linux(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert detect_platform() == Platform.LINUX


def test_detect_platform_defaults_unknown_systems_to_linux(monkeypatch):
    # Matches the pre-existing behavior of the ternaries this replaced —
    # anything that isn't Windows or Darwin falls back to the Linux branch
    # (e.g. other POSIX systems), never silently crashes.
    monkeypatch.setattr("platform.system", lambda: "SunOS")
    assert detect_platform() == Platform.LINUX


def test_platform_values_match_the_backend_os_field_literals():
    # backend/datasentinel_backend/api/v1/schemas.py's os fields validate
    # against pattern="^(windows|linux|macos)$" — these must stay in sync.
    assert {p.value for p in Platform} == {"windows", "linux", "macos"}
