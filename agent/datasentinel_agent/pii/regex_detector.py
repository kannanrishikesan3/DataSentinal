"""The always-available PII detector: regex candidates -> validators ->
context scoring. Works with zero external dependencies, so the scanner is
fully functional even if Presidio isn't installed/configured.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from datasentinel_agent.core.enums import DetectionMethod, PIICategory
from datasentinel_agent.pii.context import context_adjustment, has_label_prefix, positive_keyword_hit
from datasentinel_agent.pii.patterns import PATTERNS
from datasentinel_agent.pii.validators import (
    validate_aadhaar,
    validate_age,
    validate_credit_card,
    validate_date_of_birth,
    validate_email,
    validate_iban,
    validate_ipv4,
    validate_ipv6,
    validate_mac_address,
    validate_pan,
    validate_ssn,
    validate_swift_bic,
)


@dataclass(frozen=True)
class PIIMatch:
    category: PIICategory
    value: str
    start: int
    end: int
    confidence: float
    detection_method: DetectionMethod


@dataclass(frozen=True)
class _DetectorConfig:
    validator: Callable[[str], bool] | None
    base_confidence: float
    require_context: bool = False


_CONFIG: dict[PIICategory, _DetectorConfig] = {
    PIICategory.EMAIL: _DetectorConfig(validate_email, 0.90),
    PIICategory.PHONE_NUMBER: _DetectorConfig(None, 0.55),
    PIICategory.CREDIT_CARD: _DetectorConfig(validate_credit_card, 0.90),
    PIICategory.AADHAAR: _DetectorConfig(validate_aadhaar, 0.92),
    PIICategory.PAN: _DetectorConfig(validate_pan, 0.92),
    PIICategory.SSN: _DetectorConfig(validate_ssn, 0.85),
    PIICategory.IBAN: _DetectorConfig(validate_iban, 0.92),
    PIICategory.SWIFT_BIC: _DetectorConfig(validate_swift_bic, 0.75),
    PIICategory.IPV4: _DetectorConfig(validate_ipv4, 0.80),
    PIICategory.IPV6: _DetectorConfig(validate_ipv6, 0.80),
    PIICategory.MAC_ADDRESS: _DetectorConfig(validate_mac_address, 0.80),
    PIICategory.BANK_ACCOUNT: _DetectorConfig(None, 0.45, require_context=True),
    PIICategory.PASSPORT: _DetectorConfig(None, 0.55, require_context=True),
    PIICategory.DRIVER_LICENSE: _DetectorConfig(None, 0.45, require_context=True),
    PIICategory.EMPLOYEE_ID: _DetectorConfig(None, 0.70),
    PIICategory.CUSTOMER_ID: _DetectorConfig(None, 0.70),
    PIICategory.USERNAME: _DetectorConfig(None, 0.40, require_context=True),
    PIICategory.PERSON: _DetectorConfig(None, 0.45, require_context=True),
    PIICategory.ADDRESS: _DetectorConfig(None, 0.60),
    PIICategory.DATE_OF_BIRTH: _DetectorConfig(validate_date_of_birth, 0.55, require_context=True),
    PIICategory.AGE: _DetectorConfig(validate_age, 0.40, require_context=True),
}


def detect(text: str) -> list[PIIMatch]:
    matches: list[PIIMatch] = []

    for category, pattern in PATTERNS.items():
        config = _CONFIG[category]
        for m in pattern.finditer(text):
            value = m.group(0)

            if config.validator is not None and not config.validator(value):
                continue

            if config.require_context and not positive_keyword_hit(category, text, m.start(), m.end()):
                continue

            delta = context_adjustment(category, text, m.start(), m.end())
            label_bonus = 0.05 if has_label_prefix(text, m.start()) else 0.0
            confidence = max(0.0, min(1.0, config.base_confidence + delta + label_bonus))
            matches.append(
                PIIMatch(
                    category=category,
                    value=value,
                    start=m.start(),
                    end=m.end(),
                    confidence=confidence,
                    detection_method=DetectionMethod.REGEX
                    if config.validator is None
                    else DetectionMethod.VALIDATED,
                )
            )

    return matches
