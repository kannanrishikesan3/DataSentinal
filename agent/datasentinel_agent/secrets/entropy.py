"""Shannon entropy helpers for detecting high-randomness strings (API keys,
tokens) that don't match a known vendor pattern."""

from __future__ import annotations

import math
import re
from collections import Counter

# Random secrets are virtually always base64/hex/alnum tokens of meaningful
# length; shorter strings are too noisy to score reliably on entropy alone.
MIN_LENGTH_FOR_ENTROPY_CHECK = 20
DEFAULT_ENTROPY_THRESHOLD = 4.0

_CANDIDATE_TOKEN_RE = re.compile(r"[A-Za-z0-9+/_=\-]{20,}")


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def is_high_entropy(value: str, threshold: float = DEFAULT_ENTROPY_THRESHOLD) -> bool:
    if len(value) < MIN_LENGTH_FOR_ENTROPY_CHECK:
        return False
    return shannon_entropy(value) >= threshold


def find_high_entropy_tokens(text: str, threshold: float = DEFAULT_ENTROPY_THRESHOLD) -> list[tuple[str, int, int]]:
    """Returns (token, start, end) for substrings that look like random
    secrets: base64/hex-charset runs with entropy above the threshold."""
    results = []
    for match in _CANDIDATE_TOKEN_RE.finditer(text):
        token = match.group(0)
        if is_high_entropy(token, threshold):
            results.append((token, match.start(), match.end()))
    return results
