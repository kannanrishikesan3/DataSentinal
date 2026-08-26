"""Central database schema (spec section 23): organizations, users,
endpoints, scans, files, findings, policies, audit_logs. Every endpoint
belongs to an organization; every finding is tied to an endpoint and scan.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from datasentinel_backend.core.types import GUID, new_uuid


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime]

    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    endpoints: Mapped[list["Endpoint"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str]
    full_name: Mapped[str | None] = mapped_column(default=None)
    role: Mapped[str] = mapped_column(default="analyst")  # admin | analyst | viewer
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime]

    organization: Mapped["Organization"] = relationship(back_populates="users")

    __table_args__ = (Index("ix_users_org_id", "org_id"),)


class Endpoint(Base):
    __tablename__ = "endpoints"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id"))
    name: Mapped[str]
    hostname: Mapped[str]
    os: Mapped[str]  # windows | linux
    os_version: Mapped[str | None] = mapped_column(default=None)
    agent_version: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="active")  # active | inactive | decommissioned
    hashed_api_token: Mapped[str]
    last_seen_at: Mapped[datetime | None] = mapped_column(default=None)
    registered_at: Mapped[datetime]
    # The single policy this endpoint should apply, set either directly by an
    # admin (PATCH /endpoints/{id}) or automatically from the enrollment
    # token's own policy_id at enroll time. Null means "no per-endpoint
    # override" — services.policies falls back to every org policy in that
    # case (the pre-existing, org-wide-only behavior).
    policy_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("policies.id"), default=None)

    organization: Mapped["Organization"] = relationship(back_populates="endpoints")
    scans: Mapped[list["Scan"]] = relationship(back_populates="endpoint", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_endpoints_org_id", "org_id"),
        UniqueConstraint("org_id", "hostname", name="uq_endpoint_org_hostname"),
    )


class EnrollmentToken(Base):
    """A reusable, expiring, revocable credential an admin hands to many
    employees at once so their agents can self-register (spec sections
    7-13), instead of the admin manually registering every endpoint by
    hand and distributing one distinct permanent token per device.

    `status` (Active/Expired/Revoked/Exhausted) is deliberately NOT a
    stored column — it's derived at read time from `revoked_at` +
    `expires_at` + `current_uses` vs `max_uses` (see
    `services.enrollment.token_status`). Storing it redundantly would let
    it drift out of sync with the fields that actually determine it (e.g.
    an "Active" row silently becoming stale once `expires_at` passes).
    """

    __tablename__ = "enrollment_tokens"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id"))
    name: Mapped[str]
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"))
    hashed_token: Mapped[str]
    expires_at: Mapped[datetime]
    max_uses: Mapped[int]
    current_uses: Mapped[int] = mapped_column(default=0)
    allowed_os: Mapped[str | None] = mapped_column(default=None)  # windows | linux | None (either)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime]
    # The policy to auto-assign to any endpoint that enrolls with this token
    # (Endpoint.policy_id is copied from here at enroll time). Null means no
    # auto-assignment — the enrolled endpoint falls back to all org policies,
    # same as a directly-registered endpoint.
    policy_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("policies.id"), default=None)

    __table_args__ = (Index("ix_enrollment_tokens_org_id", "org_id"),)


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id"))
    endpoint_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("endpoints.id"))
    # The agent's own locally-generated scan id (a UUID string, see
    # agent/datasentinel_agent/core/pipeline.py). Nullable for older rows
    # ingested before this existed; when present it's the idempotency key
    # that lets a retried/duplicate upload (spec section 53 — offline
    # queue/retry) resolve to the same server-side Scan instead of creating
    # a second one. Unique per endpoint, not globally, since two different
    # endpoints legitimately generate colliding UUIDs with probability zero
    # but there's no reason to couple them even in principle.
    agent_scan_id: Mapped[str | None] = mapped_column(default=None)
    profile: Mapped[str]
    status: Mapped[str]  # pending | running | completed | cancelled | failed | timed_out
    scan_paths: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    files_discovered: Mapped[int] = mapped_column(default=0)
    files_scanned: Mapped[int] = mapped_column(default=0)
    files_skipped: Mapped[int] = mapped_column(default=0)
    pii_findings: Mapped[int] = mapped_column(default=0)
    secret_findings: Mapped[int] = mapped_column(default=0)
    severity_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_at: Mapped[datetime]

    endpoint: Mapped["Endpoint"] = relationship(back_populates="scans")
    files: Mapped[list["FileRecord"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    errors: Mapped[list["ScanError"]] = relationship(back_populates="scan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_scans_org_id", "org_id"),
        Index("ix_scans_endpoint_id", "endpoint_id"),
        UniqueConstraint("endpoint_id", "agent_scan_id", name="uq_scans_endpoint_agent_scan_id"),
    )


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    scan_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("scans.id"))
    path: Mapped[str]
    filename: Mapped[str]
    extension: Mapped[str]
    mime_type: Mapped[str | None] = mapped_column(default=None)
    size_bytes: Mapped[int]
    sha256: Mapped[str | None] = mapped_column(default=None)
    owner: Mapped[str | None] = mapped_column(default=None)
    permissions: Mapped[str | None] = mapped_column(default=None)
    risk_severity: Mapped[str | None] = mapped_column(default=None)
    risk_score: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime | None] = mapped_column(default=None)
    modified_at: Mapped[datetime | None] = mapped_column(default=None)

    scan: Mapped["Scan"] = relationship(back_populates="files")

    __table_args__ = (Index("ix_files_scan_id", "scan_id"),)


class ScanError(Base):
    """A per-file error the agent hit while scanning (permission denied,
    unreadable/corrupt file, parser failure, ...) — surfaced in the scan
    report's "Errors" section (spec section 29). Mirrors the agent's own
    local `scan_errors` table."""

    __tablename__ = "scan_errors"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    scan_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("scans.id"))
    path: Mapped[str]
    error_type: Mapped[str]
    message: Mapped[str]
    occurred_at: Mapped[datetime]

    scan: Mapped["Scan"] = relationship(back_populates="errors")

    __table_args__ = (Index("ix_scan_errors_scan_id", "scan_id"),)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id"))
    endpoint_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("endpoints.id"))
    scan_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("scans.id"))
    file_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("files.id"), default=None)
    file_path: Mapped[str]
    file_hash: Mapped[str | None] = mapped_column(default=None)
    category: Mapped[str]
    is_secret: Mapped[bool] = mapped_column(default=False)
    severity: Mapped[str]
    confidence: Mapped[float]
    occurrence_count: Mapped[int] = mapped_column(default=1)
    page_number: Mapped[int | None] = mapped_column(default=None)
    line_number: Mapped[int | None] = mapped_column(default=None)
    sheet_name: Mapped[str | None] = mapped_column(default=None)
    detection_method: Mapped[str]
    redacted_evidence: Mapped[str]
    detected_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(default="open")

    scan: Mapped["Scan"] = relationship(back_populates="findings")

    __table_args__ = (
        Index("ix_findings_org_id", "org_id"),
        Index("ix_findings_endpoint_id", "endpoint_id"),
        Index("ix_findings_scan_id", "scan_id"),
        Index("ix_findings_severity", "severity"),
        Index("ix_findings_category", "category"),
        Index("ix_findings_status", "status"),
    )


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id"))
    name: Mapped[str]
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    __table_args__ = (
        Index("ix_policies_org_id", "org_id"),
        UniqueConstraint("org_id", "name", name="uq_policy_org_name"),
    )


class ExclusionRule(Base):
    """False-positive management action 3/4 (spec section 31): excludes
    future findings matching a category and/or a file path pattern, in
    addition to the per-finding false_positive/suppressed/reopened status
    changes on `Finding`. At least one of category/path_pattern is required
    (enforced in the pydantic request schema)."""

    __tablename__ = "exclusion_rules"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id"))
    category: Mapped[str | None] = mapped_column(default=None)
    path_pattern: Mapped[str | None] = mapped_column(default=None)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"))
    reason: Mapped[str]
    created_at: Mapped[datetime]

    __table_args__ = (Index("ix_exclusion_rules_org_id", "org_id"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("organizations.id"))
    actor_type: Mapped[str]  # user | endpoint | system
    actor_id: Mapped[str | None] = mapped_column(default=None)
    action: Mapped[str]
    target_type: Mapped[str | None] = mapped_column(default=None)
    target_id: Mapped[str | None] = mapped_column(default=None)
    details: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime]

    __table_args__ = (Index("ix_audit_logs_org_id", "org_id"), Index("ix_audit_logs_action", "action"))
