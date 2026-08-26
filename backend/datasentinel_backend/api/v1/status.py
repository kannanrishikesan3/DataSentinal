"""GET /api/v1/status — authenticated system status (distinct from the
unauthenticated `/health` liveness check)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import Endpoint, Scan, User
from datasentinel_backend.security.dependencies import get_current_user

router = APIRouter(tags=["status"])


@router.get("/status")
def get_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    endpoints_total = db.scalar(select(func.count()).select_from(Endpoint).where(Endpoint.org_id == user.org_id)) or 0
    active_endpoints = db.scalar(
        select(func.count()).select_from(Endpoint).where(Endpoint.org_id == user.org_id, Endpoint.status == "active")
    ) or 0
    scans_total = db.scalar(select(func.count()).select_from(Scan).where(Scan.org_id == user.org_id)) or 0

    return {
        "organization_id": str(user.org_id),
        "endpoints_total": endpoints_total,
        "endpoints_active": active_endpoints,
        "scans_total": scans_total,
    }
