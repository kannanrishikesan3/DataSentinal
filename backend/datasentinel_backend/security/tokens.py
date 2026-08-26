"""JWT issuance/verification (dashboard users) and endpoint API token
generation/hashing (agent-to-backend auth). Endpoint tokens are shown to the
administrator exactly once at registration and stored only as a hash —
identical treatment to a password, since it's a long-lived bearer credential.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from datasentinel_backend.security.passwords import hash_password, verify_password

JWT_ALGORITHM = "HS256"


class InvalidToken(Exception):
    pass


def create_access_token(subject: str, secret_key: str, expires_minutes: int, extra_claims: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=expires_minutes)}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> dict:
    try:
        return jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidToken(str(exc)) from exc


_TOKEN_PREFIX = "dsat"


def generate_endpoint_api_token(endpoint_id) -> str:
    """A high-entropy bearer token, shown once, given to the agent to
    authenticate future requests. The endpoint ID is embedded (in plaintext,
    it isn't secret on its own) so the server can find which row's hash to
    verify against — bcrypt hashes aren't independently look-up-able."""
    return f"{_TOKEN_PREFIX}_{endpoint_id}_{secrets.token_urlsafe(32)}"


def parse_endpoint_api_token(token: str) -> str | None:
    """Returns the embedded endpoint ID (as a string) or None if the token
    isn't shaped like one of ours — never raises on malformed input."""
    parts = token.split("_", 2)
    if len(parts) != 3 or parts[0] != _TOKEN_PREFIX:
        return None
    return parts[1]


def hash_api_token(token: str) -> str:
    return hash_password(token)  # bcrypt is a fine KDF for this too


def verify_api_token(token: str, hashed: str) -> bool:
    return verify_password(token, hashed)


_ENROLLMENT_TOKEN_PREFIX = "dset"


def generate_enrollment_token(token_id) -> str:
    """A reusable enrollment credential (spec section 8) — same shape as an
    endpoint API token (id embedded in plaintext for lookup, secret part
    only ever stored as a hash), but a different prefix so the two can
    never be confused with each other at a glance or in a log line."""
    return f"{_ENROLLMENT_TOKEN_PREFIX}_{token_id}_{secrets.token_urlsafe(32)}"


def parse_enrollment_token(token: str) -> str | None:
    parts = token.split("_", 2)
    if len(parts) != 3 or parts[0] != _ENROLLMENT_TOKEN_PREFIX:
        return None
    return parts[1]
