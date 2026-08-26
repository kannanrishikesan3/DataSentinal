"""A logging filter that scrubs sensitive-looking values out of every log
record before it's emitted — defense in depth on top of the pipeline never
constructing a log message with a raw value in the first place (spec section
35: "no raw PII in logs, no secrets in logs").
"""

from __future__ import annotations

import logging
import re

# Deliberately broad, low-precision patterns — false positives (over-
# redacting) are the safe failure mode for a log scrubber; false negatives
# are not. This is NOT the detection engine (pii/secrets modules) and isn't
# held to the same precision bar.
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[REDACTED_NUMBER]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[REDACTED_JWT]"),
]


def redact(message: str) -> str:
    for pattern, replacement in _PATTERNS:
        message = pattern.sub(replacement, message)
    return message


class RedactionFilter(logging.Filter):
    """Rewrites `record.msg`/`record.args` so the formatted output never
    contains an obviously sensitive value, regardless of what the caller
    accidentally passed in."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            formatted = record.getMessage()
        except Exception:
            return True  # never let a bad log call crash the logger

        redacted = redact(formatted)
        if redacted != formatted:
            record.msg = redacted
            record.args = ()
        return True
