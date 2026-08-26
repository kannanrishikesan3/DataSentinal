"""Candidate regex patterns per PII category. These are intentionally
permissive (they find *candidates*); `validators.py` and `context.py` do the
work of deciding whether a candidate is actually sensitive."""

from __future__ import annotations

import re

from datasentinel_agent.core.enums import PIICategory

PATTERNS: dict[PIICategory, re.Pattern] = {
    PIICategory.EMAIL: re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    PIICategory.PHONE_NUMBER: re.compile(
        r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}[\s.-]?\d{0,4}(?!\d)"
    ),
    PIICategory.AADHAAR: re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)"),
    PIICategory.PAN: re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    PIICategory.SSN: re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    PIICategory.CREDIT_CARD: re.compile(r"(?<!\d)(?:\d[\s-]?){13,19}(?!\d)"),
    PIICategory.BANK_ACCOUNT: re.compile(r"(?<!\d)\d{8,17}(?!\d)"),
    PIICategory.IBAN: re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b"),
    PIICategory.SWIFT_BIC: re.compile(r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),
    PIICategory.IPV4: re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    PIICategory.IPV6: re.compile(r"\b(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}\b"),
    PIICategory.MAC_ADDRESS: re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"),
    PIICategory.PASSPORT: re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
    PIICategory.DRIVER_LICENSE: re.compile(r"\b[A-Z0-9]{6,15}\b"),
    PIICategory.EMPLOYEE_ID: re.compile(r"\b(?:EMP|E)[-_]?\d{3,8}\b", re.IGNORECASE),
    PIICategory.CUSTOMER_ID: re.compile(r"\b(?:CUST|C)[-_]?\d{3,8}\b", re.IGNORECASE),
    PIICategory.DATE_OF_BIRTH: re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b"),
    PIICategory.AGE: re.compile(r"(?<!\d)\d{1,3}(?!\d)"),
    PIICategory.USERNAME: re.compile(r"\b[a-zA-Z][a-zA-Z0-9._-]{2,31}\b"),
    # Person names and addresses are the two categories where plain regex is
    # weakest — Presidio's NLP-based recognizer is the primary source for
    # these when available (see presidio_engine.py); this is a conservative
    # fallback for "Name: <Capitalized Words>" style labeled fields.
    PIICategory.PERSON: re.compile(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3}\b"),
    PIICategory.ADDRESS: re.compile(
        r"\b\d{1,6}\s+[A-Za-z0-9.\s]{3,40}\b(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd)\b",
        re.IGNORECASE,
    ),
}
