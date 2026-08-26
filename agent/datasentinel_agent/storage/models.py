"""SQLAlchemy ORM models for the local agent database (spec section 21):
scans, files, findings, scan_errors, policies, agent_events.

Raw sensitive values are never stored — `findings.redacted_evidence` is the
only representation of a detected value, by construction (the pipeline never
even constructs a `Finding` with a raw value in the first place).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ScanRecord(Base):
    __tablename__ = "scans"

    scan_id: Mapped[str] = mapped_column(primary_key=True)
    profile: Mapped[str]
    status: Mapped[str]
    scan_paths: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime]
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    files_discovered: Mapped[int] = mapped_column(default=0)
    files_scanned: Mapped[int] = mapped_column(default=0)
    files_skipped: Mapped[int] = mapped_column(default=0)
    pii_findings: Mapped[int] = mapped_column(default=0)
    secret_findings: Mapped[int] = mapped_column(default=0)
    severity_counts: Mapped[dict] = mapped_column(JSON, default=dict)

    files: Mapped[list["FileRecordORM"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    findings: Mapped[list["FindingORM"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    errors: Mapped[list["ScanErrorORM"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class FileRecordORM(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.scan_id"))
    path: Mapped[str]
    filename: Mapped[str]
    extension: Mapped[str]
    mime_type: Mapped[str | None] = mapped_column(default=None)
    size_bytes: Mapped[int]
    created_at: Mapped[datetime | None] = mapped_column(default=None)
    modified_at: Mapped[datetime | None] = mapped_column(default=None)
    owner: Mapped[str | None] = mapped_column(default=None)
    permissions: Mapped[str | None] = mapped_column(default=None)
    sha256: Mapped[str | None] = mapped_column(default=None)
    risk_severity: Mapped[str | None] = mapped_column(default=None)
    risk_score: Mapped[int | None] = mapped_column(default=None)

    scan: Mapped["ScanRecord"] = relationship(back_populates="files")

    __table_args__ = (Index("ix_files_scan_id", "scan_id"), Index("ix_files_sha256", "sha256"))


class FindingORM(Base):
    __tablename__ = "findings"

    finding_id: Mapped[str] = mapped_column(primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.scan_id"))
    endpoint_id: Mapped[str | None] = mapped_column(default=None)
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

    scan: Mapped["ScanRecord"] = relationship(back_populates="findings")

    __table_args__ = (
        Index("ix_findings_scan_id", "scan_id"),
        Index("ix_findings_severity", "severity"),
        Index("ix_findings_category", "category"),
        Index("ix_findings_status", "status"),
    )


class ScanErrorORM(Base):
    __tablename__ = "scan_errors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.scan_id"))
    path: Mapped[str]
    error_type: Mapped[str]
    message: Mapped[str]
    occurred_at: Mapped[datetime]

    scan: Mapped["ScanRecord"] = relationship(back_populates="errors")

    __table_args__ = (Index("ix_scan_errors_scan_id", "scan_id"),)


class PolicyORM(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class AgentEventORM(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str]
    message: Mapped[str]
    occurred_at: Mapped[datetime]
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, default=None)
