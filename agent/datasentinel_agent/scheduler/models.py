"""Schedule configuration. Stored as JSON (not SQLite) — this is operational
config analogous to `config/default.yaml`'s scan profiles, not scan/finding
data, so it doesn't belong in the spec's `agent_events`/`scans`/etc. tables.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ScheduleType(StrEnum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class ScheduleConfig(BaseModel):
    id: str
    name: str
    schedule_type: ScheduleType
    enabled: bool = True
    scan_profile: str = "standard"
    scan_paths: list[str] | None = None  # None = OS default include paths

    run_at: datetime | None = None  # ONCE
    time_of_day: str | None = None  # DAILY / WEEKLY, "HH:MM" 24h
    day_of_week: int | None = Field(default=None, ge=0, le=6)  # WEEKLY, 0=Monday
    interval_seconds: int | None = Field(default=None, gt=0)  # CUSTOM

    last_run_at: datetime | None = None
    next_run_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_fields_for_type(self) -> "ScheduleConfig":
        if self.schedule_type == ScheduleType.ONCE and self.run_at is None:
            raise ValueError("run_at is required for a 'once' schedule")
        if self.schedule_type in (ScheduleType.DAILY, ScheduleType.WEEKLY) and self.time_of_day is None:
            raise ValueError(f"time_of_day is required for a '{self.schedule_type}' schedule")
        if self.schedule_type == ScheduleType.WEEKLY and self.day_of_week is None:
            raise ValueError("day_of_week is required for a 'weekly' schedule")
        if self.schedule_type == ScheduleType.CUSTOM and self.interval_seconds is None:
            raise ValueError("interval_seconds is required for a 'custom' schedule")
        return self
