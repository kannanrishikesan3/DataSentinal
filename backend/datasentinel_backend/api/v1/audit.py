"""GET /api/v1/audit-logs — the Audit Logs dashboard page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import AuditLogResponse, PaginatedAuditLogs
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import AuditLog, User
from datasentinel_backend.security.dependencies import get_current_user

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=PaginatedAuditLogs)
def list_audit_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str | None = Query(None, description="Case-insensitive substring search on action or target type"),
    limit: int = 100,
    offset: int = 0,
) -> PaginatedAuditLogs:
    stmt = select(AuditLog).where(AuditLog.org_id == user.org_id)
    if q:
        stmt = stmt.where(or_(AuditLog.action.ilike(f"%{q}%"), AuditLog.target_type.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).offset(max(offset, 0))
    items = list(db.execute(stmt).scalars())
    return PaginatedAuditLogs(total=total, items=items)
