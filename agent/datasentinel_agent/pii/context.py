"""Context-based confidence adjustment (spec section 13): `Phone: 9876543210`
should score higher than `Order ID: 9876543210`. We look at a small window of
text around a match for category-supporting and category-competing keywords.
"""

from __future__ import annotations

import re

from datasentinel_agent.core.enums import PIICategory

_WINDOW_CHARS = 40

# Keywords that, when found near a candidate, support the given category.
POSITIVE_KEYWORDS: dict[PIICategory, list[str]] = {
    PIICategory.PHONE_NUMBER: ["phone", "mobile", "cell", "tel", "contact no", "fax"],
    PIICategory.EMAIL: ["email", "e-mail", "mail"],
    PIICategory.SSN: ["ssn", "social security"],
    PIICategory.AADHAAR: ["aadhaar", "aadhar", "uidai", "uid"],
    PIICategory.PAN: ["pan", "permanent account"],
    PIICategory.PASSPORT: ["passport"],
    PIICategory.DRIVER_LICENSE: ["driver", "license", "licence", "dl no"],
    PIICategory.CREDIT_CARD: ["card", "visa", "mastercard", "amex", "credit", "debit"],
    PIICategory.BANK_ACCOUNT: ["account", "acct", "iban", "routing"],
    PIICategory.IBAN: ["iban"],
    PIICategory.SWIFT_BIC: ["swift", "bic"],
    PIICategory.DATE_OF_BIRTH: ["dob", "birth", "born"],
    PIICategory.AGE: ["age"],
    PIICategory.EMPLOYEE_ID: ["employee", "emp id", "staff id"],
    PIICategory.CUSTOMER_ID: ["customer", "client id", "cust id"],
    PIICategory.USERNAME: ["username", "user id", "login"],
    PIICategory.PERSON: ["name", "employee", "customer", "contact", "attn"],
    PIICategory.ADDRESS: ["address", "street", "residence"],
}

# Keywords that suggest the number/value is something OTHER than the
# category being considered (reduces confidence rather than rejecting
# outright, since the same digits genuinely can be ambiguous).
COMPETING_KEYWORDS: dict[PIICategory, list[str]] = {
    PIICategory.PHONE_NUMBER: ["order", "invoice", "ticket", "id", "reference", "tracking", "zip", "postal"],
    PIICategory.CREDIT_CARD: ["order", "invoice", "ticket", "tracking"],
    PIICategory.BANK_ACCOUNT: ["order", "invoice", "ticket", "tracking", "zip", "postal"],
    PIICategory.AADHAAR: ["order", "invoice", "ticket", "tracking", "phone", "mobile"],
    PIICategory.AGE: ["order", "invoice", "id", "count", "quantity", "price", "amount"],
}


def _window(text: str, start: int, end: int) -> str:
    return text[max(0, start - _WINDOW_CHARS) : min(len(text), end + _WINDOW_CHARS)].lower()


def positive_keyword_hit(category: PIICategory, text: str, start: int, end: int) -> bool:
    """True only if a keyword *specific to this category* (e.g. "phone" for
    PHONE_NUMBER) appears nearby — unlike `has_label_prefix`, a generic
    "Reference: ..." or "Quantity: ..." label does not count."""
    window = _window(text, start, end)
    return any(keyword in window for keyword in POSITIVE_KEYWORDS.get(category, []))


def context_adjustment(category: PIICategory, text: str, start: int, end: int) -> float:
    """Returns a confidence delta in roughly [-0.25, +0.20]."""
    window = _window(text, start, end)
    delta = 0.0

    if positive_keyword_hit(category, text, start, end):
        delta += 0.20

    for keyword in COMPETING_KEYWORDS.get(category, []):
        if keyword in window:
            delta -= 0.25
            break

    return delta


def has_label_prefix(text: str, start: int) -> bool:
    """True if the match is directly preceded by a `Label:` style prefix,
    e.g. "Phone: 9876543210" — a strong signal the value is what it's
    labeled as rather than an incidental number."""
    prefix = text[max(0, start - 25) : start]
    return bool(re.search(r"[A-Za-z][A-Za-z \t]{1,20}:\s*$", prefix))
