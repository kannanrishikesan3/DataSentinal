"""Phase 5 tests: aggregation into Findings (occurrence_count, redaction,
severity baseline, and never storing a raw sensitive value)."""

from datasentinel_agent.core.enums import PIICategory, Severity
from datasentinel_agent.core.schema import FileRecord
from datasentinel_agent.parsers.base import ExtractedUnit
from datasentinel_agent.pii.detector import detect_pii_in_units


def _file_record(tmp_path):
    f = tmp_path / "employees.csv"
    f.write_text("placeholder")
    return FileRecord(path=str(f), filename=f.name, extension=".csv", size_bytes=1, sha256="deadbeef")


def test_aggregates_multiple_occurrences_into_one_finding(tmp_path):
    units = [
        ExtractedUnit(text="Email: alice.synthetic@example.com", line_number=1),
        ExtractedUnit(text="Backup contact email: alice.synthetic@example.com", line_number=5),
    ]
    findings = detect_pii_in_units(units, scan_id="scan-1", file_record=_file_record(tmp_path), use_presidio=False)

    email_findings = [f for f in findings if f.category == PIICategory.EMAIL.value]
    assert len(email_findings) == 1
    assert email_findings[0].occurrence_count == 2


def test_finding_never_contains_raw_value(tmp_path):
    units = [ExtractedUnit(text="Email: bob.synthetic@example.com", line_number=1)]
    findings = detect_pii_in_units(units, scan_id="scan-1", file_record=_file_record(tmp_path), use_presidio=False)

    email_finding = next(f for f in findings if f.category == PIICategory.EMAIL.value)
    assert "bob.synthetic@example.com" not in email_finding.redacted_evidence
    assert email_finding.redacted_evidence.startswith("bo")


def test_finding_carries_baseline_severity_for_category(tmp_path):
    units = [ExtractedUnit(text="Aadhaar Number: 2341 2341 2346", line_number=1)]
    findings = detect_pii_in_units(units, scan_id="scan-1", file_record=_file_record(tmp_path), use_presidio=False)

    aadhaar_finding = next(f for f in findings if f.category == PIICategory.AADHAAR.value)
    assert aadhaar_finding.severity == Severity.HIGH


def test_findings_carry_file_and_scan_identifiers(tmp_path):
    record = _file_record(tmp_path)
    units = [ExtractedUnit(text="Email: carol.synthetic@example.com", line_number=1)]
    findings = detect_pii_in_units(units, scan_id="scan-42", file_record=record, endpoint_id="ep-1", use_presidio=False)

    finding = findings[0]
    assert finding.scan_id == "scan-42"
    assert finding.endpoint_id == "ep-1"
    assert finding.file_path == record.path
    assert finding.file_hash == "deadbeef"


def test_no_findings_for_clean_text(tmp_path):
    units = [ExtractedUnit(text="This document contains no sensitive information at all.", line_number=1)]
    findings = detect_pii_in_units(units, scan_id="scan-1", file_record=_file_record(tmp_path), use_presidio=False)
    assert findings == []
