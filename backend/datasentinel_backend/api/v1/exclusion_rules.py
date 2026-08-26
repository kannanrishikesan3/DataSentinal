"""Exclusion rules — false-positive management action 3/4 (spec section 31):
mark as false positive / suppress / create exclusion rule / reopen. The
first, second, and fourth are generic `Finding.status` transitions (see
`api/v1/findings.py`); this router adds the third, a standing rule that
excludes future findings matching a category and/or a file path pattern.
Any authenticated dashboard user may manage these (not admin-only —
analysts create these routinely).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import ExclusionRuleIn, ExclusionRuleResponse
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import ExclusionRule, User
from datasentinel_backend.security.dependencies import get_current_user, require_not_viewer
from datasentinel_backend.services.audit import log_action

router = APIRouter(prefix="/exclusion-rules", tags=["exclusion-rules"])


@router.post("", response_model=ExclusionRuleResponse, status_code=status.HTTP_201_CREATED)
def create_exclusion_rule(
    payload: ExclusionRuleIn, db: Session = Depends(get_db), user: User = Depends(require_not_viewer)
) -> ExclusionRule:
    rule = ExclusionRule(
        org_id=user.org_id,
        category=payload.category,
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
        details={"category": rule.category, "path_pattern": rule.path_pattern},
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.get("", response_model=list[ExclusionRuleResponse])
def list_exclusion_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ExclusionRule]:
    stmt = select(ExclusionRule).where(ExclusionRule.org_id == user.org_id).order_by(ExclusionRule.created_at.desc())
    return list(db.execute(stmt).scalars())


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exclusion_rule(
    rule_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_not_viewer)
) -> None:
    rule = db.get(ExclusionRule, rule_id)
    if rule is None or rule.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exclusion rule not found")

    log_action(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        action="exclusion_rule.deleted", target_type="exclusion_rule", target_id=rule.id,
        details={"category": rule.category, "path_pattern": rule.path_pattern},
    )
    db.delete(rule)
    db.commit()
