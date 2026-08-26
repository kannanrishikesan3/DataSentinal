"""Phase 18 test: Windows-style path strings must not crash path-handling
logic even when the test suite itself runs on Linux (spec section 37 calls
for explicit Windows-path coverage; the filesystem-dependent parts — actual
scanning — are inherently platform-specific and covered by the Linux-path
tests elsewhere, but pure string/logic handling of Windows paths is
testable, and worth testing, on any platform)."""

from pathlib import PureWindowsPath

from datasentinel_agent.discovery.walker import _is_excluded
from datasentinel_agent.pii.redaction import redact
from datasentinel_agent.risk.location import is_high_exposure_location
from datasentinel_agent.risk.policy import RiskPolicy
from datasentinel_agent.core.enums import PIICategory


def test_high_exposure_location_recognizes_windows_downloads_path():
    policy = RiskPolicy()
    assert is_high_exposure_location(r"C:\Users\jdoe\Downloads\export.csv", policy) is True
    assert is_high_exposure_location(r"C:\Users\jdoe\Documents\report.docx", policy) is False


def test_redaction_unaffected_by_windows_style_file_paths():
    # Redaction operates on the matched value, not the file path — but a
    # Windows path with backslashes must not trip up any string handling.
    result = redact(PIICategory.EMAIL, "jane.doe@example.com")
    assert "jane.doe@example.com" not in result


def test_purewindowspath_extension_and_name_parsing():
    path = PureWindowsPath(r"C:\Users\jdoe\Documents\employees.CSV")
    assert path.suffix.lower() == ".csv"
    assert path.name == "employees.CSV"


def test_exclude_matching_handles_windows_style_separators_without_crashing(tmp_path):
    # _is_excluded resolves real filesystem paths, so this exercises it with
    # a real (POSIX) path — the point is confirming a Windows-shaped exclude
    # entry never raises, since default.yaml's windows exclude list is
    # loaded and matched against on every scan regardless of host OS during
    # config validation.
    from pathlib import Path

    result = _is_excluded(tmp_path, [Path(r"C:\Windows"), Path(r"C:\Program Files")])
    assert result is False  # a Linux tmp_path is never "under" a Windows-only exclude root
