"""GET /api/v1/audit-logs — the Audit Logs dashboard page."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import AuditLogResponse
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import AuditLog, User
from datasentinel_backend.security.dependencies import get_current_user

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    db: Session = Depends(get_db), user: User = Depends(get_current_user), limit: int = 100
) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.org_id == user.org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 500))
    )
    return list(db.execute(stmt).scalars())
