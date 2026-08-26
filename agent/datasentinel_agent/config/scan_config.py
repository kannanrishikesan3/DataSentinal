"""Loader for the operational scan configuration (`agent/config/default.yaml`).

This covers scan profiles (quick/standard/deep), default include/exclude paths per
OS, and supported file extensions. Kept separate from `settings.py` (secrets/
environment) so this file can be safely reviewed, diffed, and overridden by policy
pushed from the backend in a later phase without touching credentials.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


class ScanProfile(BaseModel):
    max_file_size_mb: int
    max_depth: int
    worker_limit: int
    scan_archives: bool = False


class ScanSettings(BaseModel):
    default_profile: str = "standard"
    profiles: dict[str, ScanProfile]
    scan_timeout_seconds: int = 3600
    follow_symlinks: bool = False
    max_workers: int = 8
    max_cpu_percent: int = 70
    # Best-effort process-wide memory cap (RLIMIT_AS), applied once at the
    # start of a scan — see `discovery.scanner`. POSIX-only; ignored on
    # Windows and never allowed to block a scan if setrlimit itself fails.
    max_memory_mb: int = 2048


class ArchiveLimitsConfig(BaseModel):
    """Decompression-bomb guard thresholds for zip-based (OOXML) formats —
    .docx/.xlsx/.pptx. See `parsers.archive_guard.check_zip_safety`."""

    max_members: int = 10_000
    max_uncompressed_bytes: int = 500 * 1024 * 1024
    max_ratio: int = 200


class AIDefaults(BaseModel):
    enabled: bool = False
    timeout_seconds: int = 15
    max_retries: int = 2


class RetentionConfig(BaseModel):
    local_days: int = 7


class RiskPolicyConfig(BaseModel):
    secret_forces_critical: bool = True
    aggregation_category_threshold: int = 3
    high_occurrence_threshold: int = 10
    low_confidence_threshold: float = 0.5
    high_exposure_location_keywords: list[str] = Field(
        default_factory=lambda: ["downloads", "desktop", "public", "shared", "temp", "tmp"]
    )


class ScanConfig(BaseModel):
    scan: ScanSettings
    include_paths: dict[str, list[str]] = Field(default_factory=dict)
    exclude_paths: dict[str, list[str]] = Field(default_factory=dict)
    supported_extensions: list[str] = Field(default_factory=list)
    # Only added to a scan's extension filter when the active profile sets
    # `scan_archives: true` (spec section 43 — archive scanning is opt-in).
    archive_extensions: list[str] = Field(default_factory=lambda: [".zip", ".tar", ".gz", ".tgz"])
    ai: AIDefaults = Field(default_factory=AIDefaults)
    risk: RiskPolicyConfig = Field(default_factory=RiskPolicyConfig)
    archive_limits: ArchiveLimitsConfig = Field(default_factory=ArchiveLimitsConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)

    def profile(self, name: str | None = None) -> ScanProfile:
        key = name or self.scan.default_profile
        try:
            return self.scan.profiles[key]
        except KeyError as exc:
            available = ", ".join(sorted(self.scan.profiles))
            raise ValueError(f"Unknown scan profile '{key}'. Available: {available}") from exc


def load_scan_config(path: Path | None = None) -> ScanConfig:
    """`path` wins if given explicitly; otherwise `DATASENTINEL_SCAN_CONFIG_PATH`
    lets a package/administrator point at an editable config outside the
    install directory (e.g. `/etc/datasentinel-agent/scan-config.yaml` from
    a .deb — see installer/linux/deb/) without rebuilding or overriding the
    bundled default. Falls back to the bundled `config/default.yaml`."""
    env_override = os.environ.get("DATASENTINEL_SCAN_CONFIG_PATH")
    config_path = path or (Path(env_override) if env_override else DEFAULT_CONFIG_PATH)
    if not config_path.is_file():
        raise FileNotFoundError(f"Scan config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return ScanConfig.model_validate(raw)
