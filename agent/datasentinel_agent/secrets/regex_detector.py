"""Secret detection: vendor-specific patterns, structural patterns (JWT,
private key blocks, DB URLs), generic assignments, and entropy fallback for
unrecognized high-randomness tokens."""

from __future__ import annotations

from dataclasses import dataclass

from datasentinel_agent.core.enums import DetectionMethod, SecretCategory
from datasentinel_agent.secrets.entropy import find_high_entropy_tokens
from datasentinel_agent.secrets.patterns import (
    CONNECTION_STRING_PATTERN,
    DATABASE_URL_PATTERN,
    JWT_PATTERN,
    PASSWORD_ASSIGNMENT_PATTERN,
    PRIVATE_KEY_BLOCK,
    SSH_PRIVATE_KEY_BLOCK,
    VENDOR_PATTERNS,
    is_placeholder_value,
)
from datasentinel_agent.secrets.validators import validate_jwt


@dataclass(frozen=True)
class SecretMatch:
    category: SecretCategory
    value: str
    start: int
    end: int
    confidence: float
    detection_method: DetectionMethod


def detect(text: str) -> list[SecretMatch]:
    matches: list[SecretMatch] = []
    claimed_spans: list[tuple[int, int]] = []

    def _claim(start: int, end: int) -> bool:
        if any(start < e and s < end for s, e in claimed_spans):
            return False
        claimed_spans.append((start, end))
        return True

    for pattern, category, confidence in VENDOR_PATTERNS:
        for m in pattern.finditer(text):
            if _claim(m.start(), m.end()):
                matches.append(
                    SecretMatch(category, m.group(0), m.start(), m.end(), confidence, DetectionMethod.REGEX)
                )

    for m in JWT_PATTERN.finditer(text):
        if validate_jwt(m.group(0)) and _claim(m.start(), m.end()):
            matches.append(
                SecretMatch(SecretCategory.JWT, m.group(0), m.start(), m.end(), 0.90, DetectionMethod.VALIDATED)
            )

    for m in PRIVATE_KEY_BLOCK.finditer(text):
        if _claim(m.start(), m.end()):
            matches.append(
                SecretMatch(SecretCategory.PRIVATE_KEY, m.group(0), m.start(), m.end(), 0.98, DetectionMethod.REGEX)
            )

    for m in SSH_PRIVATE_KEY_BLOCK.finditer(text):
        if _claim(m.start(), m.end()):
            matches.append(
                SecretMatch(SecretCategory.SSH_KEY, m.group(0), m.start(), m.end(), 0.98, DetectionMethod.REGEX)
            )

    for m in DATABASE_URL_PATTERN.finditer(text):
        if _claim(m.start(), m.end()):
            matches.append(
                SecretMatch(
                    SecretCategory.DATABASE_URL, m.group(0), m.start(), m.end(), 0.90, DetectionMethod.REGEX
                )
            )

    for m in CONNECTION_STRING_PATTERN.finditer(text):
        if _claim(m.start(), m.end()):
            matches.append(
                SecretMatch(
                    SecretCategory.CONNECTION_STRING, m.group(0), m.start(), m.end(), 0.80, DetectionMethod.REGEX
                )
            )

    for m in PASSWORD_ASSIGNMENT_PATTERN.finditer(text):
        value = m.group(2)
        if is_placeholder_value(value):
            continue
        if _claim(m.start(), m.end()):
            matches.append(
                SecretMatch(
                    SecretCategory.PASSWORD_ASSIGNMENT, m.group(0), m.start(), m.end(), 0.65, DetectionMethod.REGEX
                )
            )

    for token, start, end in find_high_entropy_tokens(text):
        if _claim(start, end):
            matches.append(
                SecretMatch(SecretCategory.GENERIC_HIGH_ENTROPY, token, start, end, 0.55, DetectionMethod.ENTROPY)
            )

    return matches
