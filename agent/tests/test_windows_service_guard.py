"""Phase 16 test: the Windows service module must refuse to import on any
non-Windows platform with a clear error, rather than failing on a missing
`pywin32`. This is the one part of windows_service.py testable on Linux —
the pywin32-dependent class body can only be exercised on real Windows.
"""

import pytest


def test_windows_service_module_raises_on_non_windows(monkeypatch):
    import platform
    import sys

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    sys.modules.pop("datasentinel_agent.service.windows_service", None)

    with pytest.raises(ImportError, match="Windows-only"):
        import datasentinel_agent.service.windows_service  # noqa: F401


def test_scheduler_event_message_is_redacted_before_logging():
    """The Windows service's `on_event` callback builds its log message the
    same way this test does — `f"DataSentinel [{name}] {data}"` — and must
    pass it through `redact()` before handing it to `servicemanager.LogInfoMsg`
    so a raw exception message from a scan failure (which can embed a file
    path, PII, or secret-shaped text) never reaches the Windows event log
    unscrubbed. This exercises that same redaction call directly, without
    needing the Windows-only `servicemanager`/`pywin32` imports.
    """
    from datasentinel_agent.logging.redaction_filter import redact

    name = "scan_failed"
    data = {"error": "failed reading /home/alice/tax_docs/ssn_export.csv: contact alice@example.com, ssn 123-45-6789"}

    message = redact(f"DataSentinel [{name}] {data}")

    assert "alice@example.com" not in message
    assert "123-45-6789" not in message
    assert "[REDACTED_EMAIL]" in message
    assert "[REDACTED_SSN]" in message
    # Non-sensitive structure is preserved.
    assert "DataSentinel [scan_failed]" in message
