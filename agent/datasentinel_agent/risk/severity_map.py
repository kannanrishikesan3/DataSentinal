"""Baseline per-category severity (spec section 17's literal examples: Private
Key/API Key -> CRITICAL, Payment Card/Aadhaar -> HIGH, Phone -> MEDIUM, ...).

This is the *starting point* a single detection carries. The full risk engine
(Phase 7) escalates/adjusts this using cross-cutting factors — occurrence
count, co-located secrets, file permissions/location — to compute the final
per-finding and per-file risk. Kept in `risk/` (not `pii/` or `secrets/`)
because both detectors depend on it and it conceptually belongs to scoring,
not detection.
"""

from __future__ import annotations

from datasentinel_agent.core.enums import PIICategory, SecretCategory, Severity

_PII_BASELINE: dict[PIICategory, Severity] = {
    # Government identifiers — high-harm, hard to reissue
    PIICategory.AADHAAR: Severity.HIGH,
    PIICategory.PAN: Severity.HIGH,
    PIICategory.PASSPORT: Severity.HIGH,
    PIICategory.DRIVER_LICENSE: Severity.HIGH,
    PIICategory.SSN: Severity.HIGH,
    # Financial
    PIICategory.CREDIT_CARD: Severity.HIGH,
    PIICategory.BANK_ACCOUNT: Severity.HIGH,
    PIICategory.IBAN: Severity.HIGH,
    PIICategory.SWIFT_BIC: Severity.HIGH,
    # Contact / identity
    PIICategory.PHONE_NUMBER: Severity.MEDIUM,
    PIICategory.ADDRESS: Severity.MEDIUM,
    PIICategory.DATE_OF_BIRTH: Severity.MEDIUM,
    PIICategory.EMPLOYEE_ID: Severity.MEDIUM,
    PIICategory.CUSTOMER_ID: Severity.MEDIUM,
    PIICategory.EMAIL: Severity.LOW,
    PIICategory.PERSON: Severity.LOW,
    PIICategory.USERNAME: Severity.LOW,
    PIICategory.AGE: Severity.LOW,
    # Network/device
    PIICategory.IPV4: Severity.INFORMATIONAL,
    PIICategory.IPV6: Severity.INFORMATIONAL,
    PIICategory.MAC_ADDRESS: Severity.INFORMATIONAL,
}

# All secrets are more severe than generic PII by policy. Known, high-
# confidence credential types are CRITICAL; heuristic/entropy-based or
# generic assignment matches (more prone to false positives) start at HIGH,
# still above any PII baseline.
_SECRET_BASELINE: dict[SecretCategory, Severity] = {
    SecretCategory.API_KEY: Severity.CRITICAL,
    SecretCategory.ACCESS_TOKEN: Severity.CRITICAL,
    SecretCategory.JWT: Severity.CRITICAL,
    SecretCategory.AWS_CREDENTIALS: Severity.CRITICAL,
    SecretCategory.PRIVATE_KEY: Severity.CRITICAL,
    SecretCategory.SSH_KEY: Severity.CRITICAL,
    SecretCategory.OAUTH_TOKEN: Severity.CRITICAL,
    SecretCategory.DATABASE_URL: Severity.CRITICAL,
    SecretCategory.CONNECTION_STRING: Severity.CRITICAL,
    SecretCategory.PASSWORD_ASSIGNMENT: Severity.HIGH,
    SecretCategory.GENERIC_HIGH_ENTROPY: Severity.HIGH,
}


def get_baseline_severity(category: PIICategory | SecretCategory) -> Severity:
    if isinstance(category, SecretCategory):
        return _SECRET_BASELINE.get(category, Severity.HIGH)
    return _PII_BASELINE.get(category, Severity.LOW)
