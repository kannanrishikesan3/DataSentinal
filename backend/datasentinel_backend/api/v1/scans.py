"""Scan submission and lookup. Scans are reported by the agent (which has
already run the scan locally, per the agent's own fully self-contained
pipeline) via `POST /scans` — this ingests the scan record plus its files and
findings in one batch. Dashboard users read scans with their JWT.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import ScanReportRequest, ScanResponse
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import Endpoint, Scan, User
from datasentinel_backend.security.dependencies import get_current_endpoint, get_current_user
from datasentinel_backend.services.scans import cancel_scan, ingest_scan_report

router = APIRouter(prefix="/scans", tags=["scans"])


def _get_org_scoped_scan(db: Session, scan_id: uuid.UUID, org_id: uuid.UUID) -> Scan:
    scan = db.get(Scan, scan_id)
    if scan is None or scan.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found")
    return scan


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
def submit_scan(
    payload: ScanReportRequest,
    db: Session = Depends(get_db),
    endpoint: Endpoint = Depends(get_current_endpoint),
) -> Scan:
    scan = ingest_scan_report(db, endpoint, payload)
    db.commit()
    db.refresh(scan)
    return scan


@router.post("/{scan_id}/cancel", response_model=ScanResponse)
def cancel_scan_route(
    scan_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Scan:
    scan = _get_org_scoped_scan(db, scan_id, user.org_id)
    scan = cancel_scan(db, scan, actor_type="user", actor_id=user.id)
    db.commit()
    db.refresh(scan)
    return scan


@router.get("", response_model=list[ScanResponse])
def list_scans(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    endpoint_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[Scan]:
    stmt = select(Scan).where(Scan.org_id == user.org_id)
    if endpoint_id is not None:
        stmt = stmt.where(Scan.endpoint_id == endpoint_id)
    stmt = stmt.order_by(Scan.requested_at.desc()).limit(min(limit, 500))
    return list(db.execute(stmt).scalars())


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Scan:
    return _get_org_scoped_scan(db, scan_id, user.org_id)
