"""JSON persistence for schedules — a handful of records, read/rewritten
wholesale on every change; no database needed.

The default path is resolved dynamically (via `default_schedules_path()`,
honoring `DATASENTINEL_SCHEDULES_PATH`) rather than bound as a plain default
argument value: Python evaluates default argument values once, at function-
definition time, so a plain `Path` default would freeze in whatever the env
var was at import time — silently ignoring later overrides (including in
tests, which would otherwise write into a real user's home directory).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from datasentinel_agent.scheduler.models import ScheduleConfig


def default_schedules_path() -> Path:
    override = os.environ.get("DATASENTINEL_SCHEDULES_PATH")
    if override:
        return Path(override)
    return Path.home() / ".datasentinel" / "schedules.json"


def load_schedules(path: Path | None = None) -> list[ScheduleConfig]:
    path = path or default_schedules_path()
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [ScheduleConfig.model_validate(item) for item in raw]


def save_schedules(schedules: list[ScheduleConfig], path: Path | None = None) -> None:
    path = path or default_schedules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(s.model_dump_json()) for s in schedules]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def upsert_schedule(schedule: ScheduleConfig, path: Path | None = None) -> None:
    path = path or default_schedules_path()
    schedules = load_schedules(path)
    schedules = [s for s in schedules if s.id != schedule.id]
    schedules.append(schedule)
    save_schedules(schedules, path)


def remove_schedule(schedule_id: str, path: Path | None = None) -> bool:
    path = path or default_schedules_path()
    schedules = load_schedules(path)
    remaining = [s for s in schedules if s.id != schedule_id]
    removed = len(remaining) != len(schedules)
    if removed:
        save_schedules(remaining, path)
    return removed
