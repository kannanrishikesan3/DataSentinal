"""Dashboard overview aggregation (spec section 25)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datasentinel_backend.models.models import Endpoint, FileRecord, Finding, Scan

_OVER_TIME_WINDOW_DAYS = 30


def compute_overview(db: Session, org_id: uuid.UUID) -> dict:
    endpoints_total = db.scalar(select(func.count()).select_from(Endpoint).where(Endpoint.org_id == org_id)) or 0

    files_scanned_total = (
        db.scalar(select(func.coalesce(func.sum(Scan.files_scanned), 0)).where(Scan.org_id == org_id)) or 0
    )

    severity_rows = db.execute(
        select(Finding.severity, func.count()).where(Finding.org_id == org_id).group_by(Finding.severity)
    ).all()
    findings_by_severity = {severity: count for severity, count in severity_rows}

    category_rows = db.execute(
        select(Finding.category, func.count()).where(Finding.org_id == org_id).group_by(Finding.category)
    ).all()
    findings_by_category = {category: count for category, count in category_rows}

    endpoint_rows = db.execute(
        select(Endpoint.name, func.count(Finding.id))
        .join(Finding, Finding.endpoint_id == Endpoint.id)
        .where(Finding.org_id == org_id)
        .group_by(Endpoint.name)
    ).all()
    findings_by_endpoint = {name: count for name, count in endpoint_rows}

    # File-type breakdown: join through Finding.file_id (added alongside
    # this dashboard fix) to the file's extension. Findings with no file_id
    # (e.g. legacy rows ingested before that column existed) are skipped
    # rather than erroring, via the inner join.
    file_type_rows = db.execute(
        select(FileRecord.extension, func.count(Finding.id))
        .join(Finding, Finding.file_id == FileRecord.id)
        .where(Finding.org_id == org_id)
        .group_by(FileRecord.extension)
    ).all()
    findings_by_file_type = {extension: count for extension, count in file_type_rows}

    # Time-series: findings detected per day over the last _OVER_TIME_WINDOW_DAYS
    # days, bucketed in Python (rather than a dialect-specific date-trunc
    # function) so this works identically on SQLite and PostgreSQL.
    window_start = datetime.now(timezone.utc) - timedelta(days=_OVER_TIME_WINDOW_DAYS)
    detected_at_rows = db.execute(
        select(Finding.detected_at).where(Finding.org_id == org_id, Finding.detected_at >= window_start)
    ).all()
    day_counts: dict[str, int] = {}
    for (detected_at,) in detected_at_rows:
        if detected_at is None:
            continue
        day = detected_at.date().isoformat()
        day_counts[day] = day_counts.get(day, 0) + 1
    findings_over_time = [{"date": day, "count": count} for day, count in sorted(day_counts.items())]

    pii_findings_total = db.scalar(
        select(func.count()).select_from(Finding).where(Finding.org_id == org_id, Finding.is_secret.is_(False))
    ) or 0
    secret_findings_total = db.scalar(
        select(func.count()).select_from(Finding).where(Finding.org_id == org_id, Finding.is_secret.is_(True))
    ) or 0

    return {
        "endpoints_total": endpoints_total,
        "files_scanned_total": files_scanned_total,
        "pii_findings_total": pii_findings_total,
        "secret_findings_total": secret_findings_total,
        "critical_findings": findings_by_severity.get("critical", 0),
        "high_findings": findings_by_severity.get("high", 0),
        "findings_by_severity": findings_by_severity,
        "findings_by_category": findings_by_category,
        "findings_by_endpoint": findings_by_endpoint,
        "findings_by_file_type": findings_by_file_type,
        "findings_over_time": findings_over_time,
    }
