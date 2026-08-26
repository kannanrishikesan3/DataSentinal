"""Discovery orchestration: walks the configured paths, collects per-file
metadata (Phase 3) concurrently with a bounded worker pool, and honors
cancellation and a wall-clock scan timeout.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from datasentinel_agent.core.schema import FileRecord, ScanError
from datasentinel_agent.discovery.config import DiscoveryConfig
from datasentinel_agent.discovery.walker import walk
from datasentinel_agent.filesystem.metadata import collect_metadata


class ScanCancelled(Exception):
    """Raised (and caught internally) when a cancellation event fires mid-scan."""


class ScanTimedOut(Exception):
    """Raised (and caught internally) when the scan exceeds its timeout."""


@dataclass
class DiscoveryResult:
    files: list[FileRecord] = field(default_factory=list)
    errors: list[ScanError] = field(default_factory=list)
    files_discovered: int = 0
    files_scanned: int = 0
    files_skipped: int = 0
    timed_out: bool = False
    cancelled: bool = False


class DiscoveryScanner:
    """Runs one discovery pass. Create a fresh instance per scan."""

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> DiscoveryResult:
        result = DiscoveryResult()
        deadline = time.monotonic() + self.config.scan_timeout_seconds

        def should_stop() -> bool:
            return self._cancel_event.is_set() or time.monotonic() > deadline

        def on_error(err: ScanError) -> None:
            result.errors.append(err)

        candidates = list(walk(self.config, on_error=on_error, should_stop=should_stop))
        result.files_discovered = len(candidates)

        if should_stop():
            result.cancelled = self._cancel_event.is_set()
            result.timed_out = not result.cancelled
            return result

        with ThreadPoolExecutor(max_workers=max(1, self.config.max_workers)) as pool:
            futures = {
                pool.submit(collect_metadata, candidate.path): candidate for candidate in candidates
            }
            for future in futures:
                if should_stop():
                    future.cancel()
                    continue
                candidate = futures[future]
                try:
                    record = future.result()
                except (OSError, PermissionError) as exc:
                    result.files_skipped += 1
                    result.errors.append(
                        ScanError(
                            path=str(candidate.path),
                            error_type=type(exc).__name__,
                            message=str(exc),
                            occurred_at=datetime.now(timezone.utc),
                        )
                    )
                    continue
                result.files.append(record)
                result.files_scanned += 1

        if self._cancel_event.is_set():
            result.cancelled = True
        elif time.monotonic() > deadline:
            result.timed_out = True

        return result

    def run_streaming(self) -> Iterator[FileRecord]:
        """Yield FileRecords as they're collected, for callers (e.g. the CLI)
        that want to process/store files incrementally rather than waiting
        for the whole scan to finish.
        """
        deadline = time.monotonic() + self.config.scan_timeout_seconds

        def should_stop() -> bool:
            return self._cancel_event.is_set() or time.monotonic() > deadline

        with ThreadPoolExecutor(max_workers=max(1, self.config.max_workers)) as pool:
            in_flight = set()
            for candidate in walk(self.config, should_stop=should_stop):
                if should_stop():
                    break
                in_flight.add(pool.submit(collect_metadata, candidate.path))
                if len(in_flight) >= self.config.max_workers * 4:
                    done, in_flight = _partition_done(in_flight)
                    for future in done:
                        record = _safe_result(future)
                        if record is not None:
                            yield record

            for future in in_flight:
                record = _safe_result(future)
                if record is not None:
                    yield record


def _partition_done(futures: set) -> tuple[list, set]:
    done = [f for f in futures if f.done()]
    remaining = futures - set(done)
    return done, remaining


def _safe_result(future) -> FileRecord | None:
    try:
        return future.result()
    except (OSError, PermissionError):
        return None
