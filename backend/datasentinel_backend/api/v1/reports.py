"""GET /api/v1/reports/{scan_id} — generates a report from the centrally
stored (org-scoped) scan and findings. `services.reports` mirrors the shape
of the agent's own local report generator (same section list from spec
section 29) independently, since the agent and backend are separate
deployable projects that never import each other's code.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import Finding, Scan, User
from datasentinel_backend.security.dependencies import get_current_user
from datasentinel_backend.services.scans import list_scan_errors

router = APIRouter(prefix="/reports", tags=["reports"])

_MEDIA_TYPES = {"json": "application/json", "csv": "text/csv", "html": "text/html", "text": "text/plain"}


@router.get("/{scan_id}")
def get_report(
    scan_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    format: str = Query("json", pattern="^(text|json|csv|html)$"),
) -> Response:
    scan = db.get(Scan, scan_id)
    if scan is None or scan.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found")

    findings = list(db.execute(select(Finding).where(Finding.scan_id == scan_id)).scalars())
    errors = list_scan_errors(db, scan_id)

    from datasentinel_backend.services.reports import generate_backend_report

    content = generate_backend_report(scan, findings, errors, format)
    return Response(content=content, media_type=_MEDIA_TYPES[format])
