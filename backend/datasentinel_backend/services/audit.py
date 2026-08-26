"""Audit logging. Every mutating action (endpoint registration, scan
ingestion, finding status changes, ...) writes one row here — this is the
data source for the dashboard's Audit Logs page.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from datasentinel_backend.models.models import AuditLog


def log_action(
    db: Session,
    *,
    org_id,
    actor_type: str,
    actor_id,
    action: str,
    target_type: str | None = None,
    target_id=None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        org_id=org_id,
        actor_type=actor_type,
        actor_id=str(actor_id) if actor_id is not None else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry
