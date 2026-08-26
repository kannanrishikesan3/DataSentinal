"""Shared enums used across the detection pipeline, storage, and reporting."""

from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# Ordering for comparisons / picking the worst severity in a set.
SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFORMATIONAL: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def max_severity(severities: list[Severity]) -> Severity:
    if not severities:
        return Severity.INFORMATIONAL
    return max(severities, key=lambda s: SEVERITY_ORDER[s])


class DetectionMethod(StrEnum):
    REGEX = "regex"
    PRESIDIO = "presidio"
    PRESIDIO_REGEX = "presidio+regex"
    ENTROPY = "entropy"
    VALIDATED = "validated"
    CONTEXT = "context"
    AI = "ai"


class FindingStatus(StrEnum):
    OPEN = "open"
    FALSE_POSITIVE = "false_positive"
    SUPPRESSED = "suppressed"
    REOPENED = "reopened"


class ScanStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ScanProfileName(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"
    CUSTOM = "custom"


class PIICategory(StrEnum):
    # Identity
    PERSON = "person"
    EMPLOYEE_ID = "employee_id"
    CUSTOMER_ID = "customer_id"
    USERNAME = "username"
    # Contact
    EMAIL = "email"
    PHONE_NUMBER = "phone_number"
    ADDRESS = "address"
    # Government identifiers
    AADHAAR = "aadhaar"
    PAN = "pan"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    SSN = "ssn"
    # Financial
    CREDIT_CARD = "credit_card"
    BANK_ACCOUNT = "bank_account"
    IBAN = "iban"
    SWIFT_BIC = "swift_bic"
    # Personal
    DATE_OF_BIRTH = "date_of_birth"
    AGE = "age"
    # Network/device
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    MAC_ADDRESS = "mac_address"


class SecretCategory(StrEnum):
    API_KEY = "api_key"
    ACCESS_TOKEN = "access_token"
    JWT = "jwt"
    AWS_CREDENTIALS = "aws_credentials"
    PRIVATE_KEY = "private_key"
    SSH_KEY = "ssh_key"
    OAUTH_TOKEN = "oauth_token"
    DATABASE_URL = "database_url"
    CONNECTION_STRING = "connection_string"
    PASSWORD_ASSIGNMENT = "password_assignment"
    GENERIC_HIGH_ENTROPY = "generic_high_entropy_secret"
