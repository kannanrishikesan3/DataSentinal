"""Phase 5 tests: Presidio integration when available, and — critically —
graceful degradation (the scanner must work fully without it)."""

import pytest

from datasentinel_agent.pii import presidio_engine
from datasentinel_agent.pii.detector import detect_pii_in_units
from datasentinel_agent.core.schema import FileRecord
from datasentinel_agent.parsers.base import ExtractedUnit


def test_presidio_availability_does_not_raise():
    # Whatever the answer, calling this must never throw.
    presidio_engine.is_available()


@pytest.mark.skipif(not presidio_engine.is_available(), reason="Presidio/spaCy model not installed")
def test_presidio_detects_person_name():
    matches = presidio_engine.detect("Employee record for Sarah Johnson, submitted yesterday.")
    categories = {m.category.value for m in matches}
    assert "person" in categories


def test_scanner_degrades_gracefully_without_presidio(monkeypatch, tmp_path):
    """Simulates Presidio being unavailable (not installed / model missing).
    Detection must still work end-to-end via the regex layer alone."""
    monkeypatch.setattr(presidio_engine, "_get_engine", lambda: None)

    f = tmp_path / "contacts.txt"
    f.write_text("placeholder")
    record = FileRecord(path=str(f), filename=f.name, extension=".txt", size_bytes=1)

    units = [ExtractedUnit(text="Email: no-presidio@example.com", line_number=1)]
    findings = detect_pii_in_units(units, scan_id="scan-1", file_record=record, use_presidio=True)

    assert any(f.category == "email" for f in findings)


def test_presidio_detect_never_raises_on_bad_engine(monkeypatch):
    monkeypatch.setattr(presidio_engine, "_get_engine", lambda: None)
    assert presidio_engine.detect("anything") == []
