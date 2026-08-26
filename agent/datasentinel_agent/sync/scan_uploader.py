"""Uploads a completed scan's report to the central backend
(`POST /api/v1/scans`) — the "Secure Upload" step of the architecture
diagram in docs/ARCHITECTURE.md. Optional and fail-safe, matching
`policy_sync`: if the backend isn't configured or isn't reachable, the scan
result simply stays local (spec section 53 — offline behavior) rather than
blocking or failing the scan that already completed successfully.

Field-for-field, this mirrors the mapping
`tests/test_agent_to_backend_integration.py` proved works end to end
against a real backend — the ORM row field names already match the
backend's `FileIn`/`FindingIn`/`ScanErrorIn` schemas by design (see
`core/schema.py`'s module docstring).
"""

from __future__ import annotations

from datasentinel_agent.config.settings import Settings
from datasentinel_agent.logging import get_logger
from datasentinel_agent.storage.models import FileRecordORM, FindingORM, ScanErrorORM, ScanRecord
from datasentinel_agent.sync.backend_client import BackendClient, BackendUnavailable

_logger = get_logger("scan_uploader")


def _file_payload(file_record: FileRecordORM) -> dict:
    return {
        "path": file_record.path,
        "filename": file_record.filename,
        "extension": file_record.extension,
        "mime_type": file_record.mime_type,
        "size_bytes": file_record.size_bytes,
        "sha256": file_record.sha256,
        "owner": file_record.owner,
        "permissions": file_record.permissions,
        "risk_severity": file_record.risk_severity,
        "risk_score": file_record.risk_score,
        "created_at": file_record.created_at.isoformat() if file_record.created_at else None,
        "modified_at": file_record.modified_at.isoformat() if file_record.modified_at else None,
    }


def _finding_payload(finding: FindingORM) -> dict:
    return {
        "finding_id": finding.finding_id,
        "file_path": finding.file_path,
        "file_hash": finding.file_hash,
        "category": finding.category,
        "is_secret": finding.is_secret,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "occurrence_count": finding.occurrence_count,
        "page_number": finding.page_number,
        "line_number": finding.line_number,
        "sheet_name": finding.sheet_name,
        "detection_method": finding.detection_method,
        "redacted_evidence": finding.redacted_evidence,
        "detected_at": finding.detected_at.isoformat(),
    }


def _error_payload(error: ScanErrorORM) -> dict:
    return {
        "path": error.path,
        "error_type": error.error_type,
        "message": error.message,
        "occurred_at": error.occurred_at.isoformat(),
    }


def build_scan_report_payload(
    scan_record: ScanRecord,
    files: list[FileRecordORM],
    findings: list[FindingORM],
    errors: list[ScanErrorORM],
) -> dict:
    return {
        # The idempotency key the backend uses to dedupe a retried upload
        # (spec section 53) — see services/scans.py's ingest_scan_report on
        # the backend side.
        "agent_scan_id": scan_record.scan_id,
        "profile": scan_record.profile,
        "status": scan_record.status,
        "scan_paths": scan_record.scan_paths,
        "started_at": scan_record.started_at.isoformat(),
        "completed_at": scan_record.completed_at.isoformat() if scan_record.completed_at else None,
        "files_discovered": scan_record.files_discovered,
        "files_scanned": scan_record.files_scanned,
        "files_skipped": scan_record.files_skipped,
        "pii_findings": scan_record.pii_findings,
        "secret_findings": scan_record.secret_findings,
        "severity_counts": scan_record.severity_counts,
        "files": [_file_payload(f) for f in files],
        "findings": [_finding_payload(f) for f in findings],
        "errors": [_error_payload(e) for e in errors],
    }


def upload_scan(
    settings: Settings,
    scan_record: ScanRecord,
    files: list[FileRecordORM],
    findings: list[FindingORM],
    errors: list[ScanErrorORM],
) -> bool:
    """Returns True on a confirmed successful upload, False otherwise
    (backend not configured, unreachable, or rejected the payload) — never
    raises. The scan itself has already completed and been stored locally
    by the time this runs, so a failed upload only means "retry later," not
    "the scan failed."
    """
    if not settings.backend_url or not settings.endpoint_token:
        return False

    payload = build_scan_report_payload(scan_record, files, findings, errors)
    try:
        with BackendClient(settings.backend_url, settings.endpoint_token) as client:
            client.submit_scan_report(payload)
    except BackendUnavailable as exc:
        _logger.info("Scan upload deferred — backend unavailable: %s", exc)
        return False

    _logger.info("Scan %s uploaded to backend", scan_record.scan_id)
    return True


def retry_pending_uploads(settings: Settings, session_factory, *, retention_days: int = 7, path=None) -> int:
    """Retries every scan queued in `sync/upload_queue.py` (spec section 53
    — offline queue). Meant to be called once per scheduler tick: cheap
    no-op when the queue is empty or the backend isn't configured, and
    every failure mode (backend down, a scan since deleted locally) is
    handled without raising — a retry attempt must never crash the
    scheduler loop.

    Returns the number of scans successfully uploaded this call.
    """
    from datasentinel_agent.storage.database import session_scope
    from datasentinel_agent.storage.repository import get_scan
    from datasentinel_agent.sync.upload_queue import dequeue, enqueue, prune_expired

    if not settings.backend_url or not settings.endpoint_token:
        return 0

    pending = prune_expired(retention_days, path)
    if not pending:
        return 0

    uploaded_count = 0
    for entry in pending:
        with session_scope(session_factory) as session:
            scan_record = get_scan(session, entry.scan_id)
            if scan_record is None:
                # The local record is gone (e.g. retention cleanup elsewhere)
                # — nothing left to retry, stop tracking it.
                dequeue(entry.scan_id, path)
                continue

            uploaded = upload_scan(
                settings, scan_record, list(scan_record.files), list(scan_record.findings), list(scan_record.errors)
            )
        if uploaded:
            dequeue(entry.scan_id, path)
            uploaded_count += 1
        else:
            enqueue(entry.scan_id, path)

    return uploaded_count
