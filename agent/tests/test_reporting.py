"""Phase 10 tests: report generation across all formats, and that reports
never leak a raw sensitive value (only redacted evidence is ever included)."""

import csv
import io
import json
from datetime import datetime, timezone

from datasentinel_agent.reporting.generator import generate_report
from datasentinel_agent.reporting.recommendations import recommend, recommend_for_file
from datasentinel_agent.core.enums import Severity
from datasentinel_agent.storage.models import FindingORM, ScanRecord


def _scan():
    return ScanRecord(
        scan_id="scan-1", profile="standard", status="completed",
        scan_paths=["/home/user"], started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc), files_discovered=5, files_scanned=5,
        files_skipped=0, pii_findings=1, secret_findings=1,
        severity_counts={"critical": 1, "high": 0, "medium": 0, "low": 1, "informational": 0},
    )


def _findings():
    now = datetime.now(timezone.utc)
    return [
        FindingORM(
            finding_id="f1", scan_id="scan-1", file_path="/home/user/employees.csv",
            category="email", is_secret=False, severity="low", confidence=0.9,
            occurrence_count=2, detection_method="regex", redacted_evidence="jo***@example.com",
            detected_at=now, status="open",
        ),
        FindingORM(
            finding_id="f2", scan_id="scan-1", file_path="/home/user/config.log",
            category="aws_credentials", is_secret=True, severity="critical", confidence=0.95,
            occurrence_count=1, detection_method="regex", redacted_evidence="[REDACTED_AWS_CREDENTIALS:20 chars]",
            detected_at=now, status="open",
        ),
    ]


def test_text_report_contains_summary_sections():
    report = generate_report(_scan(), _findings(), "text")
    assert "DataSentinel Scan Report" in report
    assert "Files scanned:    5" in report
    assert "Critical: 1" in report
    assert "Low: 1" in report
    assert "Recommendations:" in report


def test_json_report_is_valid_and_complete():
    report = generate_report(_scan(), _findings(), "json")
    data = json.loads(report)
    assert data["scan_id"] == "scan-1"
    assert len(data["findings"]) == 2
    assert data["severity_distribution"]["critical"] == 1


def test_csv_report_has_one_row_per_finding():
    report = generate_report(_scan(), _findings(), "csv")
    rows = list(csv.reader(io.StringIO(report)))
    assert rows[0][0] == "finding_id"
    assert len(rows) == 3  # header + 2 findings


def test_html_report_is_well_formed_and_escaped():
    report = generate_report(_scan(), _findings(), "html")
    assert "<html>" in report
    assert "DataSentinel Scan Report" in report
    assert "jo***@example.com" in report


def test_reports_never_contain_raw_secret_value():
    for fmt in ("text", "json", "csv", "html"):
        report = generate_report(_scan(), _findings(), fmt)
        assert "AKIA" not in report  # no raw AWS key material anywhere


def test_unsupported_format_raises():
    import pytest

    with pytest.raises(ValueError):
        generate_report(_scan(), _findings(), "yaml")


def test_recommend_secret_gets_rotation_advice():
    advice = recommend("aws_credentials", is_secret=True, severity=Severity.CRITICAL)
    assert "rotate" in advice.lower()


def test_recommend_for_file_deduplicates():
    advice = recommend_for_file({"email", "phone_number"}, has_secret=False, severity=Severity.MEDIUM)
    assert len(advice) == len(set(advice))
