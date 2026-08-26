"""Enrollment token management (spec sections 8-9): create/list/revoke the
reusable credentials admins hand out so many endpoints can self-register
via `POST /endpoints/enroll` from one token, instead of one permanent
credential per device created by hand.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import (
    EnrollmentTokenCreateRequest,
    EnrollmentTokenCreateResponse,
    EnrollmentTokenResponse,
)
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import EnrollmentToken, Policy, User
from datasentinel_backend.security.dependencies import require_admin
from datasentinel_backend.security.tokens import generate_enrollment_token, hash_api_token
from datasentinel_backend.services.audit import log_action
from datasentinel_backend.services.enrollment import token_status

router = APIRouter(prefix="/enrollment-tokens", tags=["enrollment-tokens"])


def _to_response(token: EnrollmentToken) -> EnrollmentTokenResponse:
    return EnrollmentTokenResponse(
        id=token.id, name=token.name, status=token_status(token), max_uses=token.max_uses,
        current_uses=token.current_uses, allowed_os=token.allowed_os, expires_at=token.expires_at,
        created_at=token.created_at, policy_id=token.policy_id,
    )


@router.post("", response_model=EnrollmentTokenCreateResponse, status_code=status.HTTP_201_CREATED)
def create_enrollment_token(
    payload: EnrollmentTokenCreateRequest, db: Session = Depends(get_db), user: User = Depends(require_admin)
) -> EnrollmentTokenCreateResponse:
    if payload.policy_id is not None:
        policy = db.get(Policy, payload.policy_id)
        if policy is None or policy.org_id != user.org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")

    now = datetime.now(timezone.utc)
    token_row = EnrollmentToken(
        id=uuid.uuid4(),
        org_id=user.org_id,
        name=payload.name,
        created_by=user.id,
        hashed_token="pending",  # replaced below once we know the row's id
        expires_at=now + timedelta(days=payload.expires_in_days),
        max_uses=payload.max_uses,
        allowed_os=payload.allowed_os,
        policy_id=payload.policy_id,
        created_at=now,
    )
    db.add(token_row)
    db.flush()  # assigns token_row.id

    raw_token = generate_enrollment_token(token_row.id)
    token_row.hashed_token = hash_api_token(raw_token)
    db.flush()

    log_action(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        action="enrollment_token.created", target_type="enrollment_token", target_id=token_row.id,
        details={"name": token_row.name, "max_uses": token_row.max_uses, "allowed_os": token_row.allowed_os},
    )
    db.commit()
    db.refresh(token_row)

    return EnrollmentTokenCreateResponse(token=_to_response(token_row), raw_token=raw_token)


@router.get("", response_model=list[EnrollmentTokenResponse])
def list_enrollment_tokens(db: Session = Depends(get_db), user: User = Depends(require_admin)) -> list[EnrollmentTokenResponse]:
    stmt = select(EnrollmentToken).where(EnrollmentToken.org_id == user.org_id).order_by(EnrollmentToken.created_at.desc())
    tokens = list(db.execute(stmt).scalars())
    return [_to_response(t) for t in tokens]


@router.post("/{token_id}/revoke", response_model=EnrollmentTokenResponse)
def revoke_enrollment_token(
    token_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)
) -> EnrollmentTokenResponse:
    token_row = db.get(EnrollmentToken, token_id)
    if token_row is None or token_row.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Enrollment token not found")

    if token_row.revoked_at is None:
        token_row.revoked_at = datetime.now(timezone.utc)
        log_action(
            db, org_id=user.org_id, actor_type="user", actor_id=user.id,
            action="enrollment_token.revoked", target_type="enrollment_token", target_id=token_row.id,
            details={"name": token_row.name},
        )
        db.commit()
        db.refresh(token_row)

    return _to_response(token_row)
