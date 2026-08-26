"""Phase 8 tests: SQLite persistence round-trips real domain objects and
never leaks a raw sensitive value into the database."""

from datetime import datetime, timezone

import pytest

from datasentinel_agent.core.enums import (
    DetectionMethod,
    FindingStatus,
    ScanStatus,
    Severity,
)
from datasentinel_agent.core.schema import FileRecord, Finding, ScanError, ScanSummary
from datasentinel_agent.risk.engine import FileRiskAssessment
from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory, session_scope
from datasentinel_agent.storage.repository import (
    get_scan,
    list_findings,
    list_scan_errors,
    save_file,
    save_findings,
    save_scan_errors,
    update_finding_status,
    upsert_scan,
)


@pytest.fixture
def session_factory():
    engine = make_engine(":memory:")
    init_db(engine)
    return make_session_factory(engine)


def _finding(category="email", severity=Severity.LOW, scan_id="scan-1"):
    return Finding(
        finding_id=f"f-{category}",
        scan_id=scan_id,
        file_path="/home/user/file.txt",
        category=category,
        severity=severity,
        confidence=0.9,
        detection_method=DetectionMethod.REGEX,
        redacted_evidence="re***ed",
        detected_at=datetime.now(timezone.utc),
    )


def test_upsert_and_get_scan(session_factory):
    summary = ScanSummary(
        scan_id="scan-1",
        profile="standard",
        started_at=datetime.now(timezone.utc),
        status=ScanStatus.RUNNING,
        scan_paths=["/home/user"],
        files_discovered=10,
    )
    with session_scope(session_factory) as session:
        upsert_scan(session, summary)

    with session_scope(session_factory) as session:
        record = get_scan(session, "scan-1")
        assert record is not None
        assert record.files_discovered == 10
        assert record.status == "running"


def test_upsert_scan_updates_existing_row(session_factory):
    base = ScanSummary(
        scan_id="scan-1", profile="standard", started_at=datetime.now(timezone.utc),
        status=ScanStatus.RUNNING, scan_paths=["/home/user"],
    )
    with session_scope(session_factory) as session:
        upsert_scan(session, base)

    completed = base.model_copy(update={"status": ScanStatus.COMPLETED, "files_scanned": 42})
    with session_scope(session_factory) as session:
        upsert_scan(session, completed)

    with session_scope(session_factory) as session:
        record = get_scan(session, "scan-1")
        assert record.status == "completed"
        assert record.files_scanned == 42


def test_save_file_with_risk_assessment(session_factory):
    file_record = FileRecord(path="/home/user/f.txt", filename="f.txt", extension=".txt", size_bytes=10)
    risk = FileRiskAssessment(
        file_path=file_record.path, severity=Severity.HIGH, score=80, has_secret=False,
        distinct_categories=2, over_permissive=False, high_exposure_location=False, contributing_factors=[],
    )
    with session_scope(session_factory) as session:
        row = save_file(session, "scan-1", file_record, risk)
        assert row.risk_severity == "high"
        assert row.risk_score == 80


def test_findings_round_trip_and_never_contain_raw_evidence(session_factory):
    finding = _finding()
    with session_scope(session_factory) as session:
        save_findings(session, [finding])

    with session_scope(session_factory) as session:
        rows = list_findings(session, scan_id="scan-1")
        assert len(rows) == 1
        assert rows[0].redacted_evidence == "re***ed"
        assert rows[0].category == "email"


def test_list_findings_filters_by_severity_and_category(session_factory):
    with session_scope(session_factory) as session:
        save_findings(
            session,
            [
                _finding(category="email", severity=Severity.LOW),
                _finding(category="aadhaar", severity=Severity.HIGH),
            ],
        )

    with session_scope(session_factory) as session:
        high_only = list_findings(session, severity="high")
        assert {f.category for f in high_only} == {"aadhaar"}

        email_only = list_findings(session, category="email")
        assert {f.category for f in email_only} == {"email"}


def test_update_finding_status(session_factory):
    with session_scope(session_factory) as session:
        save_findings(session, [_finding()])

    with session_scope(session_factory) as session:
        updated = update_finding_status(session, "f-email", FindingStatus.FALSE_POSITIVE)
        assert updated.status == "false_positive"

    with session_scope(session_factory) as session:
        rows = list_findings(session, status="false_positive")
        assert len(rows) == 1


def test_scan_errors_round_trip(session_factory):
    error = ScanError(path="/home/user/locked.txt", error_type="permission_denied", message="denied", occurred_at=datetime.now(timezone.utc))
    with session_scope(session_factory) as session:
        save_scan_errors(session, "scan-1", [error])

    with session_scope(session_factory) as session:
        errors = list_scan_errors(session, "scan-1")
        assert len(errors) == 1
        assert errors[0].error_type == "permission_denied"


def test_session_scope_rolls_back_on_exception(session_factory):
    with pytest.raises(ValueError):
        with session_scope(session_factory) as session:
            save_findings(session, [_finding()])
            raise ValueError("boom")

    with session_scope(session_factory) as session:
        assert list_findings(session) == []
