"""The scheduler's run loop. Designed to be driven either by a foreground CLI
command (`datasentinel schedule run`) or, in Phase 16, the Windows Service /
systemd unit's main thread — `run_forever()` blocks until `stop()` is called
from another thread (or a signal handler).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from datasentinel_agent.config.scan_config import load_scan_config
from datasentinel_agent.config.settings import get_settings
from datasentinel_agent.core.pipeline import ScanOptions, run_scan
from datasentinel_agent.scheduler.cpu_guard import is_cpu_over_threshold
from datasentinel_agent.scheduler.models import ScheduleConfig, ScheduleType
from datasentinel_agent.scheduler.next_run import compute_next_run
from datasentinel_agent.scheduler.store import default_schedules_path, load_schedules, save_schedules
from datasentinel_agent.sync.scan_uploader import retry_pending_uploads

EventCallback = Callable[[str, dict], None]


class SchedulerService:
    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        schedules_path: Path | None = None,
        poll_interval_seconds: float = 30.0,
        max_cpu_percent: int = 70,
        on_event: EventCallback | None = None,
    ):
        self._session_factory = session_factory
        self._schedules_path = schedules_path or default_schedules_path()
        self._poll_interval = poll_interval_seconds
        self._max_cpu_percent = max_cpu_percent
        self._on_event = on_event
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _emit(self, name: str, data: dict) -> None:
        if self._on_event:
            self._on_event(name, data)

    def _retry_pending_uploads(self) -> None:
        # Spec section 53 — offline queue: retries any previously-failed
        # scan upload on every tick. Cheap no-op when the backend isn't
        # configured or the queue is empty; any failure here must never
        # interrupt the schedule-checking loop below.
        try:
            settings = get_settings()
            retention_days = load_scan_config().retention.local_days
            uploaded = retry_pending_uploads(settings, self._session_factory, retention_days=retention_days)
            if uploaded:
                self._emit("pending_uploads_retried", {"uploaded": uploaded})
        except Exception as exc:  # noqa: BLE001 - must never break the scheduler loop
            self._emit("pending_upload_retry_failed", {"error": str(exc)})

    def run_forever(self) -> None:
        self._emit("scheduler_started", {"poll_interval_seconds": self._poll_interval})
        while not self._stop_event.is_set():
            self.tick()
            self._stop_event.wait(self._poll_interval)
        self._emit("scheduler_stopped", {})

    def tick(self) -> None:
        """Runs one check of every schedule. Public so tests (and a
        `schedule run --once` mode) can drive it deterministically instead
        of waiting on the poll loop."""
        self._retry_pending_uploads()

        schedules = load_schedules(self._schedules_path)
        now = datetime.now(timezone.utc)
        changed = False

        for schedule in schedules:
            if not schedule.enabled:
                continue

            if schedule.next_run_at is None:
                schedule.next_run_at = compute_next_run(schedule, now=now)
                changed = True
                continue

            if schedule.next_run_at > now:
                continue

            if is_cpu_over_threshold(self._max_cpu_percent):
                self._emit("scan_skipped_cpu_throttle", {"schedule_id": schedule.id})
                continue  # retried on the next poll — no state change

            self._fire(schedule, now)
            changed = True

        if changed:
            save_schedules(schedules, self._schedules_path)

    def _fire(self, schedule: ScheduleConfig, now: datetime) -> None:
        self._emit("scan_triggered", {"schedule_id": schedule.id, "name": schedule.name})

        options = ScanOptions(
            profile=schedule.scan_profile,
            paths=[Path(p) for p in schedule.scan_paths] if schedule.scan_paths else None,
        )
        try:
            summary = run_scan(options, self._session_factory)
            self._emit("scan_completed", {"schedule_id": schedule.id, "scan_id": summary.scan_id})
        except Exception as exc:  # noqa: BLE001 - one bad scheduled run must not kill the scheduler
            self._emit("scan_failed", {"schedule_id": schedule.id, "error": str(exc)})

        schedule.last_run_at = now
        if schedule.schedule_type == ScheduleType.ONCE:
            schedule.enabled = False
            schedule.next_run_at = None
        else:
            schedule.next_run_at = compute_next_run(schedule, now=now)
