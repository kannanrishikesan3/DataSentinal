"""Persistence functions: convert pipeline domain objects (`core.schema`) to
ORM rows and back, plus the query helpers the CLI/reporting layer needs.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_agent.core.enums import FindingStatus
from datasentinel_agent.core.schema import FileRecord, Finding, ScanError, ScanSummary
from datasentinel_agent.risk.engine import FileRiskAssessment
from datasentinel_agent.storage.models import (
    FileRecordORM,
    FindingORM,
    ScanErrorORM,
    ScanRecord,
)


def upsert_scan(session: Session, summary: ScanSummary) -> ScanRecord:
    record = session.get(ScanRecord, summary.scan_id)
    if record is None:
        record = ScanRecord(scan_id=summary.scan_id)
        session.add(record)

    record.profile = summary.profile
    record.status = summary.status.value
    record.scan_paths = summary.scan_paths
    record.started_at = summary.started_at
    record.completed_at = summary.completed_at
    record.files_discovered = summary.files_discovered
    record.files_scanned = summary.files_scanned
    record.files_skipped = summary.files_skipped
    record.pii_findings = summary.pii_findings
    record.secret_findings = summary.secret_findings
    record.severity_counts = {k.value: v for k, v in summary.severity_counts.items()}
    session.flush()
    return record


def save_file(
    session: Session,
    scan_id: str,
    file_record: FileRecord,
    risk: FileRiskAssessment | None = None,
) -> FileRecordORM:
    row = FileRecordORM(
        scan_id=scan_id,
        path=file_record.path,
        filename=file_record.filename,
        extension=file_record.extension,
        mime_type=file_record.mime_type,
        size_bytes=file_record.size_bytes,
        created_at=file_record.created_at,
        modified_at=file_record.modified_at,
        owner=file_record.owner,
        permissions=file_record.permissions,
        sha256=file_record.sha256,
        risk_severity=risk.severity.value if risk else None,
        risk_score=risk.score if risk else None,
    )
    session.add(row)
    session.flush()
    return row


def save_findings(session: Session, findings: list[Finding]) -> list[FindingORM]:
    rows = []
    for finding in findings:
        row = FindingORM(
            finding_id=finding.finding_id,
            scan_id=finding.scan_id,
            endpoint_id=finding.endpoint_id,
            file_path=finding.file_path,
            file_hash=finding.file_hash,
            category=finding.category,
            is_secret=finding.is_secret,
            severity=finding.severity.value,
            confidence=finding.confidence,
            occurrence_count=finding.occurrence_count,
            page_number=finding.page_number,
            line_number=finding.line_number,
            sheet_name=finding.sheet_name,
            detection_method=finding.detection_method.value,
            redacted_evidence=finding.redacted_evidence,
            detected_at=finding.detected_at,
            status=finding.status.value,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def save_scan_errors(session: Session, scan_id: str, errors: list[ScanError]) -> None:
    for error in errors:
        session.add(
            ScanErrorORM(
                scan_id=scan_id,
                path=error.path,
                error_type=error.error_type,
                message=error.message,
                occurred_at=error.occurred_at,
            )
        )
    session.flush()


def get_scan(session: Session, scan_id: str) -> ScanRecord | None:
    return session.get(ScanRecord, scan_id)


def list_scans(session: Session, limit: int = 50) -> list[ScanRecord]:
    stmt = select(ScanRecord).order_by(ScanRecord.started_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars())


def list_findings(
    session: Session,
    *,
    scan_id: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    status: str | None = None,
    is_secret: bool | None = None,
    limit: int = 500,
) -> list[FindingORM]:
    stmt = select(FindingORM)
    if scan_id is not None:
        stmt = stmt.where(FindingORM.scan_id == scan_id)
    if severity is not None:
        stmt = stmt.where(FindingORM.severity == severity)
    if category is not None:
        stmt = stmt.where(FindingORM.category == category)
    if status is not None:
        stmt = stmt.where(FindingORM.status == status)
    if is_secret is not None:
        stmt = stmt.where(FindingORM.is_secret == is_secret)
    stmt = stmt.order_by(FindingORM.detected_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars())


def update_finding_status(session: Session, finding_id: str, status: FindingStatus) -> FindingORM | None:
    row = session.get(FindingORM, finding_id)
    if row is None:
        return None
    row.status = status.value
    session.flush()
    return row


def list_scan_errors(session: Session, scan_id: str) -> list[ScanErrorORM]:
    stmt = select(ScanErrorORM).where(ScanErrorORM.scan_id == scan_id)
    return list(session.execute(stmt).scalars())
