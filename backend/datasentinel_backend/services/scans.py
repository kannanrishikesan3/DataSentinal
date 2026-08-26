"""Scan ingestion: the agent calls this once a local scan finishes (or with
intermediate status while running). One request creates the Scan row and
ingests its files + findings in a single batch.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import ScanReportRequest
from datasentinel_backend.models.models import Endpoint, FileRecord, Finding, Scan, ScanError
from datasentinel_backend.services.audit import log_action


def ingest_scan_report(db: Session, endpoint: Endpoint, payload: ScanReportRequest) -> Scan:
    # Idempotency (spec section 53 — "prevent duplicate uploads"): a scan
    # already ingested under this (endpoint, agent_scan_id) pair is returned
    # as-is rather than re-ingested. This is what makes the agent's retry
    # queue (sync/upload_queue.py) safe to retry blindly after a network
    # failure that might have actually succeeded server-side before the
    # response was lost.
    if payload.agent_scan_id is not None:
        existing = db.scalar(
            select(Scan).where(Scan.endpoint_id == endpoint.id, Scan.agent_scan_id == payload.agent_scan_id)
        )
        if existing is not None:
            return existing

    scan = Scan(
        org_id=endpoint.org_id,
        endpoint_id=endpoint.id,
        agent_scan_id=payload.agent_scan_id,
        profile=payload.profile,
        status=payload.status,
        scan_paths=payload.scan_paths,
        started_at=payload.started_at,
        completed_at=payload.completed_at,
        files_discovered=payload.files_discovered,
        files_scanned=payload.files_scanned,
        files_skipped=payload.files_skipped,
        pii_findings=payload.pii_findings,
        secret_findings=payload.secret_findings,
        severity_counts=payload.severity_counts,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(scan)
    db.flush()

    file_records: list[FileRecord] = []
    for file_in in payload.files:
        file_record = FileRecord(scan_id=scan.id, **file_in.model_dump())
        db.add(file_record)
        file_records.append(file_record)
    db.flush()  # assigns each file_record.id, needed to correlate findings below

    # The agent's scan report doesn't carry a separate stable file
    # identifier shared between its `files` and `findings` lists, so
    # correlate by file_path within this same scan to look up the
    # just-inserted FileRecord.
    file_id_by_path = {file_record.path: file_record.id for file_record in file_records}

    for finding_in in payload.findings:
        data = finding_in.model_dump(exclude={"finding_id"})
        db.add(
            Finding(
                org_id=endpoint.org_id,
                endpoint_id=endpoint.id,
                scan_id=scan.id,
                file_id=file_id_by_path.get(data["file_path"]),
                **data,
            )
        )

    for error_in in payload.errors:
        db.add(ScanError(scan_id=scan.id, **error_in.model_dump()))

    endpoint.last_seen_at = datetime.now(timezone.utc)
    db.flush()

    log_action(
        db,
        org_id=endpoint.org_id,
        actor_type="endpoint",
        actor_id=endpoint.id,
        action="scan.ingested",
        target_type="scan",
        target_id=scan.id,
        details={"status": scan.status, "findings": len(payload.findings)},
    )

    return scan


def list_scan_errors(db: Session, scan_id: uuid.UUID) -> list[ScanError]:
    stmt = select(ScanError).where(ScanError.scan_id == scan_id).order_by(ScanError.occurred_at)
    return list(db.execute(stmt).scalars())


def cancel_scan(db: Session, scan: Scan, *, actor_type: str, actor_id) -> Scan:
    scan.status = "cancelled"
    db.flush()
    log_action(
        db, org_id=scan.org_id, actor_type=actor_type, actor_id=actor_id,
        action="scan.cancel_requested", target_type="scan", target_id=scan.id,
    )
    return scan
