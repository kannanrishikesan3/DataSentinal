"""User authentication: POST /api/v1/auth/login issues a JWT dashboard
session token. There is no unauthenticated way to reach any other route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datasentinel_backend.api.v1.schemas import CurrentUserResponse, LoginRequest, TokenResponse
from datasentinel_backend.core.config import get_settings
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import User
from datasentinel_backend.security.dependencies import get_current_user
from datasentinel_backend.security.passwords import verify_password
from datasentinel_backend.security.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))

    # Constant-shape response whether the email exists or not — don't leak
    # which emails are registered via a differently timed/shaped error.
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    settings = get_settings()
    token = create_access_token(
        subject=str(user.id),
        secret_key=settings.secret_key,
        expires_minutes=settings.access_token_expire_minutes,
        extra_claims={"org_id": str(user.org_id), "role": user.role},
    )
    return TokenResponse(access_token=token, expires_in_minutes=settings.access_token_expire_minutes)


@router.get("/me", response_model=CurrentUserResponse)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user
