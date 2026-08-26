"""Discovery configuration: include/exclude paths, filters, and resource limits.

Wraps the operational YAML config (`datasentinel_agent.config.scan_config`) into
the concrete parameters a scan run needs, resolving OS-specific default paths.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from datasentinel_agent.config.scan_config import ScanConfig, load_scan_config
from datasentinel_agent.core.platform import detect_platform


def _current_os_key() -> str:
    return detect_platform().value


def resolve_default_include_paths(config: ScanConfig | None = None) -> list[Path]:
    config = config or load_scan_config()
    raw_paths = config.include_paths.get(_current_os_key(), [])
    resolved = []
    for raw in raw_paths:
        expanded = os.path.expandvars(os.path.expanduser(raw))
        path = Path(expanded)
        if path.exists():
            resolved.append(path)
    return resolved


def resolve_default_exclude_paths(config: ScanConfig | None = None) -> list[Path]:
    config = config or load_scan_config()
    raw_paths = config.exclude_paths.get(_current_os_key(), [])
    return [Path(os.path.expandvars(os.path.expanduser(p))) for p in raw_paths]


class DiscoveryConfig(BaseModel):
    include_paths: list[Path]
    exclude_paths: list[Path] = Field(default_factory=list)
    extension_filter: set[str] | None = None  # None = all supported extensions
    max_file_size_bytes: int = 50 * 1024 * 1024
    max_depth: int = 10
    follow_symlinks: bool = False
    max_workers: int = 8
    scan_timeout_seconds: int = 3600

    @classmethod
    def from_profile(
        cls,
        profile_name: str | None = None,
        *,
        include_paths: list[Path] | None = None,
        exclude_paths: list[Path] | None = None,
        config: ScanConfig | None = None,
    ) -> "DiscoveryConfig":
        config = config or load_scan_config()
        profile = config.profile(profile_name)
        extension_filter = set(config.supported_extensions)
        if profile.scan_archives:
            extension_filter |= set(config.archive_extensions)
        return cls(
            include_paths=include_paths or resolve_default_include_paths(config),
            exclude_paths=exclude_paths or resolve_default_exclude_paths(config),
            extension_filter=extension_filter,
            max_file_size_bytes=profile.max_file_size_mb * 1024 * 1024,
            max_depth=profile.max_depth,
            follow_symlinks=config.scan.follow_symlinks,
            max_workers=profile.worker_limit,
            scan_timeout_seconds=config.scan.scan_timeout_seconds,
        )
