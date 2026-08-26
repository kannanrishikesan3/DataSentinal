"""Finding listing, lookup, and status changes (mark false positive /
suppress / reopen — spec section 31). Every status change is audit-logged.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import (
    ExclusionRuleResponse,
    FindingExclusionRuleRequest,
    FindingResponse,
    FindingStatusUpdateRequest,
    PaginatedFindings,
)
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import ExclusionRule, FileRecord, Finding, User
from datasentinel_backend.security.dependencies import get_current_user, require_not_viewer
from datasentinel_backend.services.audit import log_action

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("", response_model=PaginatedFindings)
def list_findings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    endpoint_id: uuid.UUID | None = None,
    scan_id: uuid.UUID | None = None,
    severity: str | None = None,
    category: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    is_secret: bool | None = None,
    file_type: str | None = None,
    detected_after: datetime | None = None,
    detected_before: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PaginatedFindings:
    stmt = select(Finding).where(Finding.org_id == user.org_id)
    if endpoint_id is not None:
        stmt = stmt.where(Finding.endpoint_id == endpoint_id)
    if scan_id is not None:
        stmt = stmt.where(Finding.scan_id == scan_id)
    if severity is not None:
        stmt = stmt.where(Finding.severity == severity)
    if category is not None:
        stmt = stmt.where(Finding.category == category)
    if status_filter is not None:
        stmt = stmt.where(Finding.status == status_filter)
    if is_secret is not None:
        stmt = stmt.where(Finding.is_secret == is_secret)
    if file_type is not None:
        extension = file_type if file_type.startswith(".") else f".{file_type}"
        stmt = stmt.where(Finding.file_id.in_(select(FileRecord.id).where(FileRecord.extension == extension)))
    if detected_after is not None:
        stmt = stmt.where(Finding.detected_at >= detected_after)
    if detected_before is not None:
        stmt = stmt.where(Finding.detected_at <= detected_before)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Finding.detected_at.desc()).limit(min(limit, 500)).offset(max(offset, 0))
    items = list(db.execute(stmt).scalars())
    return PaginatedFindings(total=total, items=items)


@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(finding_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None or finding.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    return finding


@router.patch("/{finding_id}", response_model=FindingResponse)
def update_finding_status(
    finding_id: uuid.UUID,
    payload: FindingStatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_not_viewer),
) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None or finding.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")

    previous_status = finding.status
    finding.status = payload.status
    db.flush()

    log_action(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        action="finding.status_changed", target_type="finding", target_id=finding.id,
        details={"from": previous_status, "to": payload.status},
    )
    db.commit()
    db.refresh(finding)
    return finding


@router.post("/{finding_id}/exclusion-rule", response_model=ExclusionRuleResponse, status_code=status.HTTP_201_CREATED)
def create_exclusion_rule_from_finding(
    finding_id: uuid.UUID,
    payload: FindingExclusionRuleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_not_viewer),
) -> ExclusionRule:
    """One-click "create exclusion rule from this finding": pre-fills the
    rule's category from the finding, so the frontend can offer this
    directly from a finding's detail view without a generic empty form."""
    finding = db.get(Finding, finding_id)
    if finding is None or finding.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")

    rule = ExclusionRule(
        org_id=user.org_id,
        category=finding.category,
        path_pattern=payload.path_pattern,
        created_by=user.id,
        reason=payload.reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(rule)
    db.flush()

    log_action(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        action="exclusion_rule.created", target_type="exclusion_rule", target_id=rule.id,
        details={"category": rule.category, "path_pattern": rule.path_pattern, "source_finding_id": str(finding.id)},
    )
    db.commit()
    db.refresh(rule)
    return rule
