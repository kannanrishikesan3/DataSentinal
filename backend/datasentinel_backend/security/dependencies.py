"""FastAPI auth dependencies. Two separate schemes on purpose: dashboard
users authenticate with a JWT (issued by `/api/v1/auth/login`); agents
authenticate with a long-lived per-endpoint API token (issued once at
`/api/v1/endpoints/register`). No unauthenticated administrative endpoint is
ever exposed — every mutating route depends on one of these.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from datasentinel_backend.core.config import get_settings
from datasentinel_backend.core.database import get_db
from datasentinel_backend.models.models import Endpoint, User
from datasentinel_backend.security.tokens import InvalidToken, decode_access_token, parse_endpoint_api_token, verify_api_token

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials, get_settings().secret_key)
    except InvalidToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token subject")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin privileges required")
    return user


def require_not_viewer(user: User = Depends(get_current_user)) -> User:
    """Blocks the read-only `viewer` role from any mutating route that isn't
    otherwise admin-gated (finding status changes, exclusion rules) — a
    viewer may see everything but change nothing. `analyst` and `admin` both
    pass."""
    if user.role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Viewers cannot perform this action")
    return user


def get_current_endpoint(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Endpoint:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    endpoint_id_str = parse_endpoint_api_token(credentials.credentials)
    if endpoint_id_str is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API token")

    try:
        endpoint_id = uuid.UUID(endpoint_id_str)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API token")

    endpoint = db.get(Endpoint, endpoint_id)
    if endpoint is None or not verify_api_token(credentials.credentials, endpoint.hashed_api_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API token")
    if endpoint.status == "decommissioned":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Endpoint has been decommissioned")
    return endpoint
