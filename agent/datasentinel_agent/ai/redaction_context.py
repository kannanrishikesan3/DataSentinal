"""Builds the minimal, redacted context sent to OpenRouter. The AI never sees
a whole file or directory — only a short window around one candidate value,
with the candidate itself and any other detected PII/secrets nearby replaced
with placeholders (spec section 15's redaction example).
"""

from __future__ import annotations

_WINDOW_CHARS = 60


def build_redacted_context(
    unit_text: str,
    candidate_start: int,
    candidate_end: int,
    category_placeholder: str,
    other_spans: list[tuple[int, int, str]] | None = None,
) -> str:
    """`other_spans` is a list of (start, end, placeholder) for any other
    sensitive matches in the same unit — these get redacted too, so a
    second, unrelated PII value never leaks into the AI request just
    because it happened to sit near the one being classified.
    """
    spans = sorted([(candidate_start, candidate_end, category_placeholder)] + (other_spans or []))

    redacted_parts = []
    cursor = 0
    for start, end, placeholder in spans:
        if start < cursor:
            continue  # overlapping span already covered
        redacted_parts.append(unit_text[cursor:start])
        redacted_parts.append(f"[{placeholder}]")
        cursor = end
    redacted_parts.append(unit_text[cursor:])
    redacted_text = "".join(redacted_parts)

    # Trim to a window around the primary candidate's new (shifted) position.
    placeholder_marker = f"[{category_placeholder}]"
    marker_pos = redacted_text.find(placeholder_marker)
    if marker_pos == -1:
        return redacted_text[: _WINDOW_CHARS * 2]

    start = max(0, marker_pos - _WINDOW_CHARS)
    end = min(len(redacted_text), marker_pos + len(placeholder_marker) + _WINDOW_CHARS)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(redacted_text) else ""
    return f"{prefix}{redacted_text[start:end]}{suffix}"
