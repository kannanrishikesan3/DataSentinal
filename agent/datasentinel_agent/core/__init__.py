"""Shared enums and domain schema used across the detection pipeline."""

from datasentinel_agent.core.enums import (
    DetectionMethod,
    FindingStatus,
    PIICategory,
    ScanProfileName,
    ScanStatus,
    SecretCategory,
    Severity,
    max_severity,
)
from datasentinel_agent.core.schema import FileRecord, Finding, ScanError, ScanSummary

__all__ = [
    "DetectionMethod",
    "FindingStatus",
    "PIICategory",
    "ScanProfileName",
    "ScanStatus",
    "SecretCategory",
    "Severity",
    "max_severity",
    "FileRecord",
    "Finding",
    "ScanError",
    "ScanSummary",
]
