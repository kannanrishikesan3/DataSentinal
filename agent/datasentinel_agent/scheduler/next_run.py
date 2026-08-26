"""Next-run-time computation for each schedule type. Pure functions, no I/O —
the trickiest part of a scheduler to get right, so kept small and unit-tested
in isolation from the service loop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from datasentinel_agent.scheduler.models import ScheduleConfig, ScheduleType


class InvalidTimeOfDay(ValueError):
    pass


def parse_time_of_day(value: str) -> tuple[int, int]:
    try:
        hour_str, minute_str = value.split(":")
        hour, minute = int(hour_str), int(minute_str)
    except ValueError as exc:
        raise InvalidTimeOfDay(f"time_of_day must be 'HH:MM', got {value!r}") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise InvalidTimeOfDay(f"time_of_day out of range: {value!r}")
    return hour, minute


def compute_next_run(schedule: ScheduleConfig, *, now: datetime | None = None) -> datetime | None:
    """Returns the next UTC datetime this schedule should fire, or None if it
    will never fire again (a 'once' schedule that has already run)."""
    now = now or datetime.now(timezone.utc)

    if schedule.schedule_type == ScheduleType.ONCE:
        if schedule.last_run_at is not None:
            return None
        return schedule.run_at

    if schedule.schedule_type == ScheduleType.DAILY:
        hour, minute = parse_time_of_day(schedule.time_of_day)
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if schedule.schedule_type == ScheduleType.WEEKLY:
        hour, minute = parse_time_of_day(schedule.time_of_day)
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (schedule.day_of_week - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    if schedule.schedule_type == ScheduleType.CUSTOM:
        base = schedule.last_run_at or now
        next_candidate = base + timedelta(seconds=schedule.interval_seconds)
        # If the agent was offline past several intervals, jump forward to
        # the next future slot rather than firing a burst of catch-up scans.
        while next_candidate <= now:
            next_candidate += timedelta(seconds=schedule.interval_seconds)
        return next_candidate

    raise ValueError(f"Unknown schedule type: {schedule.schedule_type}")  # pragma: no cover
