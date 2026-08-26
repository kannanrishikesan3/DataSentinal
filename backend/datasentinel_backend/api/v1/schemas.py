"""Request/response models for the `/api/v1` API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


# --- Auth --------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime


# --- Endpoints -----------------------------------------------------------------


class EndpointRegisterRequest(BaseModel):
    name: str
    hostname: str
    os: str = Field(pattern="^(windows|linux|macos)$")
    os_version: str | None = None
    agent_version: str | None = None


class EndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    hostname: str
    os: str
    os_version: str | None
    agent_version: str | None
    status: str
    last_seen_at: datetime | None
    registered_at: datetime
    last_scan: datetime | None = None  # completed_at of the endpoint's most recent completed scan, or null
    risk_score: int = 0  # see services.endpoints.compute_risk_score for the exact computation
    policy_id: uuid.UUID | None = None  # assigned directly or copied from the enrollment token used, if any


class EndpointRegisterResponse(BaseModel):
    endpoint: EndpointResponse
    api_token: str  # shown exactly once


class EndpointUpdateRequest(BaseModel):
    """Admin-only: assign or clear this endpoint's policy override. Every
    other endpoint field is set at registration/enrollment time and isn't
    editable here."""

    policy_id: uuid.UUID | None = None


# --- Enrollment tokens (spec sections 7-13) -------------------------------------


class EnrollmentTokenCreateRequest(BaseModel):
    name: str
    expires_in_days: int = Field(gt=0, le=365, default=7)
    max_uses: int = Field(gt=0, le=100_000, default=1)
    allowed_os: str | None = Field(default=None, pattern="^(windows|linux|macos)$")
    # If set, every endpoint that enrolls with this token gets this policy
    # auto-assigned (Endpoint.policy_id) instead of falling back to every
    # org policy.
    policy_id: uuid.UUID | None = None


class EnrollmentTokenResponse(BaseModel):
    """Never carries the raw token — only `EnrollmentTokenCreateResponse`
    (the one-time creation response) does."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str  # active | expired | revoked | exhausted — computed, see services.enrollment
    max_uses: int
    current_uses: int
    allowed_os: str | None
    expires_at: datetime
    created_at: datetime
    policy_id: uuid.UUID | None = None


class EnrollmentTokenCreateResponse(BaseModel):
    token: EnrollmentTokenResponse
    raw_token: str  # shown exactly once — never retrievable again


class EndpointEnrollRequest(BaseModel):
    """What an agent submits to self-register using an enrollment token,
    instead of an admin calling `POST /endpoints/register` on its behalf."""

    enrollment_token: str
    name: str
    hostname: str
    os: str = Field(pattern="^(windows|linux|macos)$")
    os_version: str | None = None
    agent_version: str | None = None


# --- Bulk endpoint import (Excel) -----------------------------------------------


class BulkImportRow(BaseModel):
    row: int
    name: str
    hostname: str
    status: str  # created | error
    api_token: str | None = None  # present only when status == "created"; shown exactly once
    error: str | None = None


class BulkImportResponse(BaseModel):
    created: int
    failed: int
    rows: list[BulkImportRow]


# --- Findings (submitted as part of a scan report) ------------------------------


class FindingIn(BaseModel):
    finding_id: str
    file_path: str
    file_hash: str | None = None
    category: str
    is_secret: bool = False
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    occurrence_count: int = 1
    page_number: int | None = None
    line_number: int | None = None
    sheet_name: str | None = None
    detection_method: str
    redacted_evidence: str
    detected_at: datetime


class FileIn(BaseModel):
    path: str
    filename: str
    extension: str
    mime_type: str | None = None
    size_bytes: int
    sha256: str | None = None
    owner: str | None = None
    permissions: str | None = None
    risk_severity: str | None = None
    risk_score: int | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None


class ScanErrorIn(BaseModel):
    path: str
    error_type: str
    message: str
    occurred_at: datetime


class ScanReportRequest(BaseModel):
    """The agent submits this once a local scan finishes (or periodically
    while running, for status other than `completed`)."""

    # The agent's own locally-generated scan id — the idempotency key for a
    # retried/duplicate upload (spec section 53). Optional so older/other
    # agent versions without it still work; without it, a retried upload is
    # not deduplicated (matches the pre-existing behavior).
    agent_scan_id: str | None = None
    profile: str
    status: str = Field(pattern="^(pending|running|completed|cancelled|failed|timed_out)$")
    scan_paths: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None
    files_discovered: int = 0
    files_scanned: int = 0
    files_skipped: int = 0
    pii_findings: int = 0
    secret_findings: int = 0
    severity_counts: dict[str, int] = Field(default_factory=dict)
    files: list[FileIn] = Field(default_factory=list)
    findings: list[FindingIn] = Field(default_factory=list)
    errors: list[ScanErrorIn] = Field(default_factory=list)


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    endpoint_id: uuid.UUID
    profile: str
    status: str
    scan_paths: list[str]
    started_at: datetime | None
    completed_at: datetime | None
    files_discovered: int
    files_scanned: int
    files_skipped: int
    pii_findings: int
    secret_findings: int
    severity_counts: dict[str, int]


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    endpoint_id: uuid.UUID
    scan_id: uuid.UUID
    file_id: uuid.UUID | None
    file_path: str
    file_hash: str | None
    category: str
    is_secret: bool
    severity: str
    confidence: float
    occurrence_count: int
    page_number: int | None
    line_number: int | None
    sheet_name: str | None
    detection_method: str
    redacted_evidence: str
    detected_at: datetime
    status: str


class FindingStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(open|false_positive|suppressed|reopened)$")


class PaginatedFindings(BaseModel):
    total: int
    items: list[FindingResponse]


# --- Dashboard / audit -----------------------------------------------------------


class FindingsOverTimePoint(BaseModel):
    date: str  # ISO date, e.g. "2026-08-26"
    count: int


class DashboardOverview(BaseModel):
    endpoints_total: int
    files_scanned_total: int
    pii_findings_total: int
    secret_findings_total: int
    critical_findings: int
    high_findings: int
    findings_by_severity: dict[str, int]
    findings_by_category: dict[str, int]
    findings_by_endpoint: dict[str, int]
    findings_by_file_type: dict[str, int]
    findings_over_time: list[FindingsOverTimePoint]


# --- Policies --------------------------------------------------------------------


class PolicyIn(BaseModel):
    name: str
    config: dict = Field(default_factory=dict)


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    config: dict
    created_at: datetime
    updated_at: datetime


class ExclusionRuleIn(BaseModel):
    category: str | None = None
    path_pattern: str | None = None
    reason: str

    @model_validator(mode="after")
    def _require_category_or_pattern(self) -> "ExclusionRuleIn":
        if not self.category and not self.path_pattern:
            raise ValueError("At least one of 'category' or 'path_pattern' must be set")
        return self


class FindingExclusionRuleRequest(BaseModel):
    """Creates an exclusion rule from a finding's context: category is
    pre-filled from the finding, path_pattern is optional (leave unset to
    exclude the whole category org-wide; set it to also scope to this
    finding's file)."""

    reason: str
    path_pattern: str | None = None


class ExclusionRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str | None
    path_pattern: str | None
    created_by: uuid.UUID
    reason: str
    created_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_type: str
    actor_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    details: dict | None
    created_at: datetime
