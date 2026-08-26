"""Enrollment token validation and status (spec sections 7-13): the
reusable, expiring, revocable credential that lets many endpoints
self-register from one token, instead of an admin manually creating one
permanent credential per device.
"""

from __future__ import annotations

from datetime import datetime, timezone

from datasentinel_backend.models.models import EnrollmentToken


class EnrollmentTokenError(Exception):
    """Raised by `validate_enrollment_token` with a human-readable reason;
    the caller (the `/endpoints/enroll` route) maps this to a 403/401 and
    audit-logs the rejection rather than silently dropping it."""


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite (used in tests and small deployments) round-trips datetimes
    as naive, dropping whatever tzinfo they were stored with — every value
    here is UTC by convention (see `security.tokens.create_access_token`
    for the same pattern), so a missing tzinfo always means UTC, never
    local time."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def token_status(token: EnrollmentToken, *, now: datetime | None = None) -> str:
    """Active / Expired / Revoked / Exhausted — computed, not stored (see
    the model's docstring for why)."""
    now = _as_aware_utc(now or datetime.now(timezone.utc))
    if token.revoked_at is not None:
        return "revoked"
    if _as_aware_utc(token.expires_at) <= now:
        return "expired"
    if token.current_uses >= token.max_uses:
        return "exhausted"
    return "active"


def validate_enrollment_token(token: EnrollmentToken, *, requested_os: str, now: datetime | None = None) -> None:
    """Raises `EnrollmentTokenError` if this token cannot be used right
    now for a device of `requested_os`. Never mutates `token` — the
    caller increments `current_uses` only after successfully creating the
    endpoint, so a failed enrollment never consumes a use."""
    status = token_status(token, now=now)
    if status != "active":
        raise EnrollmentTokenError(f"Enrollment token is {status}")
    if token.allowed_os is not None and token.allowed_os != requested_os:
        raise EnrollmentTokenError(f"This token only allows '{token.allowed_os}' endpoints, not '{requested_os}'")
