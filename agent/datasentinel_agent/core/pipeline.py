"""End-to-end scan orchestration: discovery -> parsing -> PII/secret
detection -> risk scoring -> local storage. This is the one place every
entry point (CLI now; scheduler and backend-triggered scans later) drives a
scan through, so the pipeline logic only exists once.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from datasentinel_agent.ai.service import AIReviewService
from datasentinel_agent.config.settings import Settings, get_settings
from datasentinel_agent.core.enums import ScanStatus
from datasentinel_agent.core.schema import Finding, ScanError, ScanSummary
from datasentinel_agent.discovery.config import DiscoveryConfig
from datasentinel_agent.discovery.scanner import DiscoveryScanner
from datasentinel_agent.logging import get_logger
from datasentinel_agent.parsers.registry import safe_extract
from datasentinel_agent.pii.detector import detect_pii_in_units
from datasentinel_agent.risk.engine import aggregate_severity_counts, assess_file_risk
from datasentinel_agent.secrets.detector import detect_secrets_in_units
from datasentinel_agent.storage.repository import get_scan, save_file, save_findings, save_scan_errors, upsert_scan
from datasentinel_agent.storage.database import session_scope
from datasentinel_agent.sync.policy_sync import sync_policies
from datasentinel_agent.sync.scan_uploader import upload_scan
from datasentinel_agent.sync.upload_queue import dequeue, enqueue


class ScanOptions(BaseModel):
    profile: str | None = None  # None -> config's default_profile
    paths: list[Path] | None = None  # None -> OS default include paths
    exclude_paths: list[Path] | None = None
    use_presidio: bool = True
    use_ai: bool = False  # wired up in Phase 11; currently a no-op
    endpoint_id: str | None = None


ProgressCallback = Callable[[str, dict], None]

_logger = get_logger("pipeline")


def _apply_memory_limit(max_memory_mb: int) -> None:
    """Best-effort, process-wide memory cap (`RLIMIT_AS`) applied once at
    the start of a scan — not per file. POSIX-only: the `resource` module
    doesn't exist on Windows, so it's imported only inside this guard and
    the whole call is a deliberate no-op there. Any failure (already-lower
    limit set by a parent process, an unsupported platform/kernel, etc.) is
    logged at debug level and swallowed — this must never block scanning.
    """
    if sys.platform == "win32":
        _logger.debug("Memory limit (RLIMIT_AS) is POSIX-only; skipping on Windows.")
        return

    try:
        import resource

        limit_bytes = max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    except Exception as exc:  # noqa: BLE001 - must never block a scan
        _logger.debug("Could not set process memory limit to %dMB: %s", max_memory_mb, exc)


def run_scan(
    options: ScanOptions,
    session_factory: sessionmaker,
    *,
    on_progress: ProgressCallback | None = None,
    settings: Settings | None = None,
) -> ScanSummary:
    scan_id = str(uuid4())
    started_at = datetime.now(timezone.utc)
    settings = settings or get_settings()

    # Centrally-pushed policies (spec section 42) layer on top of the local
    # config/default.yaml. A no-op (returns the local config unchanged)
    # whenever the backend isn't configured or isn't reachable — this must
    # never block a scan.
    scan_config = sync_policies(settings)

    _apply_memory_limit(scan_config.scan.max_memory_mb)

    ai_service = AIReviewService(settings) if options.use_ai else None

    discovery_config = DiscoveryConfig.from_profile(
        options.profile, include_paths=options.paths, exclude_paths=options.exclude_paths, config=scan_config,
    )
    scan_paths = [str(p) for p in discovery_config.include_paths]
    profile_name = options.profile or "standard"

    with session_scope(session_factory) as session:
        upsert_scan(
            session,
            ScanSummary(
                scan_id=scan_id,
                profile=profile_name,
                started_at=started_at,
                status=ScanStatus.RUNNING,
                scan_paths=scan_paths,
            ),
        )

    _logger.info("Scan %s started (profile=%s, paths=%d)", scan_id, profile_name, len(scan_paths))
    if on_progress:
        on_progress("discovery_started", {"paths": scan_paths})

    scanner = DiscoveryScanner(discovery_config)
    discovery_result = scanner.run()

    _logger.info("Scan %s discovery complete: %d files found", scan_id, discovery_result.files_discovered)
    if on_progress:
        on_progress("discovery_completed", {"files_discovered": discovery_result.files_discovered})

    all_findings: list[Finding] = []
    all_errors: list[ScanError] = list(discovery_result.errors)
    files_skipped = discovery_result.files_skipped

    for file_record in discovery_result.files:
        units, parse_error = safe_extract(Path(file_record.path))
        if parse_error is not None:
            files_skipped += 1
            all_errors.append(
                ScanError(
                    path=file_record.path,
                    error_type="parse_error",
                    message=str(parse_error),
                    occurred_at=datetime.now(timezone.utc),
                )
            )
            # Path only — never the parser's exception text verbatim, which
            # could echo back file content for certain malformed-input errors.
            _logger.warning("Scan %s: failed to parse %s", scan_id, file_record.path)
            continue

        pii_findings = detect_pii_in_units(
            units, scan_id=scan_id, file_record=file_record,
            endpoint_id=options.endpoint_id, use_presidio=options.use_presidio,
        )
        secret_findings = detect_secrets_in_units(
            units, scan_id=scan_id, file_record=file_record, endpoint_id=options.endpoint_id,
        )
        file_findings = pii_findings + secret_findings
        if ai_service is not None and ai_service.enabled:
            file_findings = [ai_service.review_finding(f) for f in file_findings]
        risk = assess_file_risk(file_findings, file_record, policy=scan_config.risk)
        all_findings.extend(file_findings)

        with session_scope(session_factory) as session:
            save_file(session, scan_id, file_record, risk)
            if file_findings:
                save_findings(session, file_findings)

        if on_progress:
            on_progress("file_scanned", {"path": file_record.path, "findings": len(file_findings)})

    with session_scope(session_factory) as session:
        # all_errors, not discovery_result.errors — it also carries the
        # per-file parse errors accumulated in the loop above; using the
        # narrower discovery-only list here would silently drop them from
        # the persisted scan_errors table even though they're in the
        # returned ScanSummary.
        save_scan_errors(session, scan_id, all_errors)

    if ai_service is not None:
        ai_service.close()

    completed_at = datetime.now(timezone.utc)
    status = ScanStatus.CANCELLED if discovery_result.cancelled else (
        ScanStatus.TIMED_OUT if discovery_result.timed_out else ScanStatus.COMPLETED
    )

    summary = ScanSummary(
        scan_id=scan_id,
        profile=profile_name,
        started_at=started_at,
        completed_at=completed_at,
        status=status,
        scan_paths=scan_paths,
        files_discovered=discovery_result.files_discovered,
        files_scanned=discovery_result.files_scanned,
        files_skipped=files_skipped,
        pii_findings=sum(1 for f in all_findings if not f.is_secret),
        secret_findings=sum(1 for f in all_findings if f.is_secret),
        severity_counts=aggregate_severity_counts(all_findings),
        errors=all_errors,
    )

    with session_scope(session_factory) as session:
        upsert_scan(session, summary)

    _logger.info(
        "Scan %s %s: %d files scanned, %d PII findings, %d secrets",
        scan_id, status.value, summary.files_scanned, summary.pii_findings, summary.secret_findings,
    )

    # Secure upload (spec sections 12/39/53): best-effort, never blocks or
    # fails the scan — it already completed and is safely stored locally.
    # Not configured / unreachable both just mean "stays local for now." The
    # broad except is deliberate defense in depth on top of `upload_scan`'s
    # own contract (it never raises) — a bug in the uploader must never
    # retroactively fail a scan that already completed and was persisted.
    if settings.backend_url and settings.endpoint_token:
        try:
            with session_scope(session_factory) as session:
                scan_record = get_scan(session, scan_id)
                if scan_record is not None:
                    uploaded = upload_scan(
                        settings, scan_record, list(scan_record.files), list(scan_record.findings), list(scan_record.errors)
                    )
                    # Offline queue (spec section 53): a failed upload is
                    # queued for the scheduler to retry later; a success
                    # dequeues it in case an earlier attempt for this same
                    # scan had previously failed and queued it.
                    (dequeue if uploaded else enqueue)(scan_id)
                    if on_progress:
                        on_progress("scan_uploaded" if uploaded else "scan_upload_deferred", {"scan_id": scan_id})
        except Exception:  # noqa: BLE001 - an upload bug must never fail an already-completed scan
            _logger.warning("Scan %s: upload step raised unexpectedly; scan result remains stored locally.", scan_id)

    if on_progress:
        on_progress("scan_completed", {"scan_id": scan_id, "status": status.value})

    return summary
