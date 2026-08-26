"""Category-aware redaction. Findings must never store/display a complete
sensitive value (spec section 18): `ri***@example.com`, `AB******23`."""

from __future__ import annotations

from datasentinel_agent.core.enums import PIICategory, SecretCategory


def _mask_middle(value: str, keep_start: int, keep_end: int, mask_char: str = "*") -> str:
    if len(value) <= keep_start + keep_end:
        return mask_char * len(value)
    middle = mask_char * (len(value) - keep_start - keep_end)
    return f"{value[:keep_start]}{middle}{value[len(value) - keep_end:]}"


def redact(category: PIICategory | SecretCategory, value: str) -> str:
    if isinstance(category, SecretCategory):
        # Never show any part of an actual secret value.
        return f"[REDACTED_{category.value.upper()}:{len(value)} chars]"

    if category == PIICategory.EMAIL:
        local, _, domain = value.partition("@")
        visible = local[:2]
        return f"{visible}{'*' * max(1, len(local) - 2)}@{domain}"

    if category in (PIICategory.CREDIT_CARD, PIICategory.BANK_ACCOUNT, PIICategory.IBAN):
        digits = value
        return _mask_middle(digits, keep_start=0, keep_end=4)

    if category == PIICategory.PAN:
        return _mask_middle(value, keep_start=2, keep_end=2)

    if category == PIICategory.AADHAAR:
        digits = value.replace(" ", "").replace("-", "")
        return _mask_middle(digits, keep_start=0, keep_end=4)

    if category == PIICategory.PHONE_NUMBER:
        return _mask_middle(value, keep_start=0, keep_end=2)

    if category == PIICategory.SSN:
        return _mask_middle(value, keep_start=0, keep_end=4)

    if category == PIICategory.PERSON:
        parts = value.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}. {parts[-1][0]}."
        return _mask_middle(value, keep_start=1, keep_end=0)

    # Generic fallback: keep a small prefix, mask the rest.
    return _mask_middle(value, keep_start=2, keep_end=2)
