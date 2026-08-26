"""In-memory / API-shape domain models shared across the detection pipeline.

These are the pipeline's working representations. `storage/` maps them to
SQLAlchemy ORM rows; `reporting/` and the CLI render them; the backend's
ingestion API (Phase 12) mirrors their shape for the finding payload it accepts.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from datasentinel_agent.core.enums import (
    DetectionMethod,
    FindingStatus,
    ScanStatus,
    Severity,
)


class FileRecord(BaseModel):
    """Metadata for one discovered file (Phase 2/3)."""

    model_config = ConfigDict(frozen=True)

    path: str
    filename: str
    extension: str
    mime_type: str | None = None
    size_bytes: int
    created_at: datetime | None = None
    modified_at: datetime | None = None
    owner: str | None = None
    permissions: str | None = None
    sha256: str | None = None


class ScanError(BaseModel):
    path: str
    error_type: str
    message: str
    occurred_at: datetime


class Finding(BaseModel):
    """A single detected PII/secret occurrence in a file."""

    model_config = ConfigDict(frozen=True)

    finding_id: str
    scan_id: str
    endpoint_id: str | None = None
    file_path: str
    file_hash: str | None = None
    category: str
    is_secret: bool = False
    severity: Severity
    confidence: float
    occurrence_count: int = 1
    page_number: int | None = None
    line_number: int | None = None
    sheet_name: str | None = None
    detection_method: DetectionMethod
    redacted_evidence: str
    detected_at: datetime
    status: FindingStatus = FindingStatus.OPEN


class ScanSummary(BaseModel):
    scan_id: str
    profile: str
    started_at: datetime
    completed_at: datetime | None = None
    status: ScanStatus
    scan_paths: list[str]
    files_discovered: int = 0
    files_scanned: int = 0
    files_skipped: int = 0
    pii_findings: int = 0
    secret_findings: int = 0
    severity_counts: dict[Severity, int] = {}
    errors: list[ScanError] = []
