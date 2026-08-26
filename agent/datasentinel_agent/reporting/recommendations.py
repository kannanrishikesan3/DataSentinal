"""Remediation recommendations. Advisory only — recommendations are text for
a human analyst to act on; this module never modifies or deletes files."""

from __future__ import annotations

from datasentinel_agent.core.enums import Severity

_CATEGORY_ADVICE: dict[str, str] = {
    "aadhaar": "Move this file to approved encrypted storage and remove unnecessary local copies of government ID data.",
    "pan": "Move this file to approved encrypted storage and remove unnecessary local copies of government ID data.",
    "ssn": "Move this file to approved encrypted storage and remove unnecessary local copies of government ID data.",
    "passport": "Move this file to approved encrypted storage and remove unnecessary local copies of government ID data.",
    "driver_license": "Move this file to approved encrypted storage and remove unnecessary local copies of government ID data.",
    "credit_card": "Payment card data should never be stored outside a PCI-compliant system. Remove this file and route the workflow through the approved payment processor.",
    "bank_account": "Move financial account data to approved encrypted storage; avoid keeping bank details in plain files.",
    "iban": "Move financial account data to approved encrypted storage; avoid keeping bank details in plain files.",
    "swift_bic": "Move financial account data to approved encrypted storage; avoid keeping bank details in plain files.",
    "email": "Review whether this contact list needs to exist locally; if it's a working export, restrict access and delete once no longer needed.",
    "phone_number": "Review whether this contact list needs to exist locally; if it's a working export, restrict access and delete once no longer needed.",
    "address": "Review whether this contact list needs to exist locally; if it's a working export, restrict access and delete once no longer needed.",
    "person": "Verify this file is authorized to contain personal data locally; move to approved storage if it's a bulk export.",
    "date_of_birth": "Treat this as sensitive personal data — restrict access and avoid retaining beyond its business need.",
}

_SECRET_ADVICE = (
    "Rotate this credential immediately and remove it from the file. Store secrets in a "
    "managed secrets vault or environment-specific configuration that is never committed "
    "or copied to endpoint storage."
)

_DEFAULT_ADVICE = "Review this file's sensitivity and restrict access or relocate it to approved storage as appropriate."


def recommend(category: str, is_secret: bool, severity: Severity) -> str:
    if is_secret:
        return _SECRET_ADVICE
    return _CATEGORY_ADVICE.get(category, _DEFAULT_ADVICE)


def recommend_for_file(categories: set[str], has_secret: bool, severity: Severity) -> list[str]:
    """De-duplicated recommendations for everything found in one file."""
    seen: list[str] = []
    if has_secret:
        seen.append(_SECRET_ADVICE)
    for category in sorted(categories):
        advice = _CATEGORY_ADVICE.get(category, _DEFAULT_ADVICE)
        if advice not in seen:
            seen.append(advice)
    return seen
