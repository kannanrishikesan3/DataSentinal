"""Endpoint listing helpers: last-scan timestamp and a simple risk score
derived from each endpoint's currently-open findings (spec section 26 —
the Endpoints page's "Last Scan" and "Risk Score" columns)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_backend.models.models import Endpoint, Finding, Scan
from datasentinel_backend.security.tokens import generate_endpoint_api_token, hash_api_token
from datasentinel_backend.services.reports import SEVERITY_ORDER


class DuplicateHostname(Exception):
    def __init__(self, hostname: str):
        self.hostname = hostname
        super().__init__(f"An endpoint with hostname '{hostname}' is already registered")


def create_endpoint(
    db: Session,
    *,
    org_id: uuid.UUID,
    name: str,
    hostname: str,
    os: str,
    os_version: str | None = None,
    agent_version: str | None = None,
    policy_id: uuid.UUID | None = None,
) -> tuple[Endpoint, str]:
    """Shared by admin-direct registration (`POST /endpoints/register`),
    enrollment-token self-registration (`POST /endpoints/enroll`), and
    bulk Excel import — one place that creates an `Endpoint` row and
    issues its API token, so all three paths stay consistent instead of
    three copies of the same six lines silently drifting apart.

    Raises `DuplicateHostname` if `(org_id, hostname)` already exists —
    callers decide how to surface that (409 for a single registration,
    a per-row error for a bulk import).
    """
    existing = db.scalar(select(Endpoint).where(Endpoint.org_id == org_id, Endpoint.hostname == hostname))
    if existing is not None:
        raise DuplicateHostname(hostname)

    endpoint = Endpoint(
        id=uuid.uuid4(),
        org_id=org_id,
        name=name,
        hostname=hostname,
        os=os,
        os_version=os_version,
        agent_version=agent_version,
        status="active",
        hashed_api_token="pending",  # replaced below once we know the row's id
        registered_at=datetime.now(timezone.utc),
        policy_id=policy_id,
    )
    db.add(endpoint)
    db.flush()  # assigns endpoint.id

    token = generate_endpoint_api_token(endpoint.id)
    endpoint.hashed_api_token = hash_api_token(token)
    db.flush()

    return endpoint, token


def get_last_scan_at(db: Session, endpoint_id: uuid.UUID) -> datetime | None:
    """The `completed_at` of this endpoint's most recently completed scan,
    or None if it has never completed one."""
    stmt = (
        select(Scan.completed_at)
        .where(Scan.endpoint_id == endpoint_id, Scan.status == "completed")
        .order_by(Scan.completed_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def compute_risk_score(db: Session, endpoint_id: uuid.UUID) -> int:
    """Risk score = the `SEVERITY_ORDER` rank (0-4, see services.reports) of
    the highest-severity currently-open finding on this endpoint; 0 if it
    has none. This reuses the same severity ranking the report generator
    uses to pick each file's "worst" finding, rather than a second scale."""
    severities = db.execute(
        select(Finding.severity).where(Finding.endpoint_id == endpoint_id, Finding.status == "open")
    ).scalars().all()
    if not severities:
        return 0
    return max(SEVERITY_ORDER.get(severity, 0) for severity in severities)
