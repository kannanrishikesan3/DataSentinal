"""Offline upload queue (spec section 53): when a scan's upload to the
backend fails, its id is recorded here so the scheduler retries it on a
later tick instead of the result being silently lost until the next scan
happens to succeed. JSON persistence, same pattern as
`scheduler/store.py` (schedules) — a handful of records, read/rewritten
wholesale, no database needed.

Retention (`retention.local_days` in config/default.yaml): an entry stops
being retried after that many days and is dropped, so a permanently
unreachable backend doesn't grow this file forever or retry indefinitely.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel


class PendingUpload(BaseModel):
    scan_id: str
    first_failed_at: datetime
    last_attempt_at: datetime
    attempts: int = 1


def default_pending_uploads_path() -> Path:
    override = os.environ.get("DATASENTINEL_PENDING_UPLOADS_PATH")
    if override:
        return Path(override)
    return Path.home() / ".datasentinel" / "pending_uploads.json"


def load_pending(path: Path | None = None) -> list[PendingUpload]:
    path = path or default_pending_uploads_path()
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [PendingUpload.model_validate(item) for item in raw]


def save_pending(pending: list[PendingUpload], path: Path | None = None) -> None:
    path = path or default_pending_uploads_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(p.model_dump_json()) for p in pending]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def enqueue(scan_id: str, path: Path | None = None) -> None:
    """Records (or bumps the attempt count on) a failed upload."""
    pending = load_pending(path)
    now = datetime.now(timezone.utc)
    existing = next((p for p in pending if p.scan_id == scan_id), None)
    if existing is not None:
        existing.attempts += 1
        existing.last_attempt_at = now
    else:
        pending.append(PendingUpload(scan_id=scan_id, first_failed_at=now, last_attempt_at=now, attempts=1))
    save_pending(pending, path)


def dequeue(scan_id: str, path: Path | None = None) -> None:
    """Removes a scan from the queue — called once its upload succeeds."""
    pending = load_pending(path)
    remaining = [p for p in pending if p.scan_id != scan_id]
    if len(remaining) != len(pending):
        save_pending(remaining, path)


def prune_expired(retention_days: int, path: Path | None = None) -> list[PendingUpload]:
    """Drops entries older than `retention_days` and returns the ones still
    eligible for retry (i.e. the pruned, current queue)."""
    pending = load_pending(path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept = [p for p in pending if p.first_failed_at >= cutoff]
    if len(kept) != len(pending):
        save_pending(kept, path)
    return kept
