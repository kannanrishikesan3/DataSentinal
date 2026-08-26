"""Structural validation for secret candidates — a shape match alone (e.g.
three dot-separated base64url segments) isn't enough to call something a JWT."""

from __future__ import annotations

import base64
import json


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded)


def validate_jwt(candidate: str) -> bool:
    parts = candidate.split(".")
    if len(parts) != 3:
        return False
    try:
        header = json.loads(_b64url_decode(parts[0]))
    except Exception:
        return False
    if not isinstance(header, dict) or "alg" not in header:
        return False
    try:
        _b64url_decode(parts[1])  # payload must at least be valid base64url
    except Exception:
        return False
    return True
