"""Policy management (spec section 2/17): named, versioned JSON config blobs
(scan profile overrides, exclusion rules, risk thresholds) an org can define
centrally. The agent's own `config/default.yaml` remains the local fallback
when no policy is pushed — this is additive, not a hard dependency.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import PolicyIn, PolicyResponse
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import Endpoint, Policy, User
from datasentinel_backend.security.dependencies import get_current_endpoint, get_current_user, require_admin
from datasentinel_backend.services.audit import log_action

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=list[PolicyResponse])
def list_policies(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Policy]:
    stmt = select(Policy).where(Policy.org_id == user.org_id).order_by(Policy.name)
    return list(db.execute(stmt).scalars())


@router.get("/effective", response_model=list[PolicyResponse])
def list_effective_policies(
    db: Session = Depends(get_db), endpoint: Endpoint = Depends(get_current_endpoint)
) -> list[Policy]:
    """The policies an agent should apply locally (spec section 42) —
    authenticated with the endpoint's own API token, not a dashboard user's
    JWT, since this is called by the agent itself rather than someone
    browsing the dashboard.

    If this endpoint has a policy assigned directly (Endpoint.policy_id, set
    at enroll time from the enrollment token's own policy_id, or later by an
    admin via PATCH /endpoints/{id}), only that one policy applies. With no
    assignment, every org policy applies — the original, org-wide-only
    behavior, preserved as the fallback.
    """
    if endpoint.policy_id is not None:
        policy = db.get(Policy, endpoint.policy_id)
        # The assigned policy may have been deleted after assignment; fall
        # back to org-wide rather than silently returning nothing.
        if policy is not None and policy.org_id == endpoint.org_id:
            return [policy]

    stmt = select(Policy).where(Policy.org_id == endpoint.org_id).order_by(Policy.name)
    return list(db.execute(stmt).scalars())


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(payload: PolicyIn, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> Policy:
    existing = db.scalar(select(Policy).where(Policy.org_id == user.org_id, Policy.name == payload.name))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A policy named '{payload.name}' already exists")

    now = datetime.now(timezone.utc)
    policy = Policy(org_id=user.org_id, name=payload.name, config=payload.config, created_at=now, updated_at=now)
    db.add(policy)
    db.flush()

    log_action(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        action="policy.created", target_type="policy", target_id=policy.id, details={"name": policy.name},
    )
    db.commit()
    db.refresh(policy)
    return policy


@router.patch("/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: uuid.UUID, payload: PolicyIn, db: Session = Depends(get_db), user: User = Depends(require_admin)
) -> Policy:
    policy = db.get(Policy, policy_id)
    if policy is None or policy.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")

    policy.name = payload.name
    policy.config = payload.config
    policy.updated_at = datetime.now(timezone.utc)
    db.flush()

    log_action(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        action="policy.updated", target_type="policy", target_id=policy.id,
    )
    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    policy_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)
) -> None:
    policy = db.get(Policy, policy_id)
    if policy is None or policy.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")

    log_action(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        action="policy.deleted", target_type="policy", target_id=policy.id, details={"name": policy.name},
    )
    db.delete(policy)
    db.commit()
