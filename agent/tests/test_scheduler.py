"""Phase 15 tests: next-run computation (the trickiest part), CPU throttling,
JSON persistence, and the service tick loop end-to-end."""

from datetime import datetime, timedelta, timezone

import pytest

from datasentinel_agent.scheduler.cpu_guard import is_cpu_over_threshold
from datasentinel_agent.scheduler.models import ScheduleConfig, ScheduleType
from datasentinel_agent.scheduler.next_run import InvalidTimeOfDay, compute_next_run, parse_time_of_day
from datasentinel_agent.scheduler.service import SchedulerService
from datasentinel_agent.scheduler.store import load_schedules, remove_schedule, save_schedules, upsert_schedule
from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory, session_scope
from datasentinel_agent.storage.repository import list_scans

UTC = timezone.utc


def test_parse_time_of_day():
    assert parse_time_of_day("09:30") == (9, 30)
    with pytest.raises(InvalidTimeOfDay):
        parse_time_of_day("25:00")
    with pytest.raises(InvalidTimeOfDay):
        parse_time_of_day("not-a-time")


def test_once_schedule_fires_at_run_at_then_never_again():
    run_at = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    schedule = ScheduleConfig(id="s1", name="one-off", schedule_type=ScheduleType.ONCE, run_at=run_at)

    now = datetime(2026, 2, 1, 0, 0, tzinfo=UTC)
    assert compute_next_run(schedule, now=now) == run_at

    schedule.last_run_at = run_at
    assert compute_next_run(schedule, now=run_at + timedelta(days=1)) is None


def test_daily_schedule_computes_today_or_tomorrow():
    schedule = ScheduleConfig(id="s2", name="nightly", schedule_type=ScheduleType.DAILY, time_of_day="02:00")

    before = datetime(2026, 3, 1, 1, 0, tzinfo=UTC)
    assert compute_next_run(schedule, now=before) == datetime(2026, 3, 1, 2, 0, tzinfo=UTC)

    after = datetime(2026, 3, 1, 3, 0, tzinfo=UTC)
    assert compute_next_run(schedule, now=after) == datetime(2026, 3, 2, 2, 0, tzinfo=UTC)


def test_weekly_schedule_lands_on_correct_day_of_week():
    # Monday=0 ... Sunday=6. 2026-03-02 is a Monday.
    schedule = ScheduleConfig(
        id="s3", name="weekly-scan", schedule_type=ScheduleType.WEEKLY, time_of_day="03:00", day_of_week=4  # Friday
    )
    monday = datetime(2026, 3, 2, 0, 0, tzinfo=UTC)
    next_run = compute_next_run(schedule, now=monday)
    assert next_run.weekday() == 4
    assert next_run.date() == datetime(2026, 3, 6, 0, 0, tzinfo=UTC).date()  # that Friday

    # If we're past this week's slot, it should roll to next week.
    just_after_friday = next_run + timedelta(minutes=1)
    following = compute_next_run(schedule, now=just_after_friday)
    assert (following - next_run).days == 7


def test_custom_interval_schedule_advances_by_interval():
    schedule = ScheduleConfig(id="s4", name="every-6h", schedule_type=ScheduleType.CUSTOM, interval_seconds=6 * 3600)
    last_run = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
    schedule.last_run_at = last_run

    next_run = compute_next_run(schedule, now=last_run + timedelta(hours=1))
    assert next_run == last_run + timedelta(hours=6)


def test_custom_interval_catches_up_without_bursting(monkeypatch=None):
    # Agent was offline for 3 days; interval is hourly. Next run should be
    # the next FUTURE slot, not a burst of 72 overdue runs.
    schedule = ScheduleConfig(id="s5", name="hourly", schedule_type=ScheduleType.CUSTOM, interval_seconds=3600)
    schedule.last_run_at = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
    now = datetime(2026, 3, 4, 0, 30, tzinfo=UTC)  # 3 days + 30 minutes later

    next_run = compute_next_run(schedule, now=now)
    assert next_run > now
    assert next_run - now <= timedelta(hours=1)


def test_schedule_requires_type_specific_fields():
    with pytest.raises(ValueError):
        ScheduleConfig(id="bad", name="x", schedule_type=ScheduleType.DAILY)  # missing time_of_day
    with pytest.raises(ValueError):
        ScheduleConfig(id="bad", name="x", schedule_type=ScheduleType.WEEKLY, time_of_day="09:00")  # missing day_of_week


def test_cpu_guard_never_raises():
    # Whatever the real answer, this must not throw in a test environment.
    result = is_cpu_over_threshold(200, interval=0.05)  # threshold no real system exceeds
    assert result is False


def test_schedule_store_round_trip(tmp_path):
    path = tmp_path / "schedules.json"
    schedule = ScheduleConfig(id="s1", name="nightly", schedule_type=ScheduleType.DAILY, time_of_day="02:00")

    upsert_schedule(schedule, path)
    loaded = load_schedules(path)
    assert len(loaded) == 1
    assert loaded[0].name == "nightly"

    updated = schedule.model_copy(update={"enabled": False})
    upsert_schedule(updated, path)
    loaded_again = load_schedules(path)
    assert len(loaded_again) == 1  # replaced, not duplicated
    assert loaded_again[0].enabled is False

    assert remove_schedule("s1", path) is True
    assert load_schedules(path) == []
    assert remove_schedule("does-not-exist", path) is False


def test_scheduler_service_fires_due_schedule_and_persists_run(tmp_path):
    scan_dir = tmp_path / "target"
    scan_dir.mkdir()
    (scan_dir / "notes.txt").write_text("Email: scheduler.test@example.com\n")

    schedules_path = tmp_path / "schedules.json"
    due_schedule = ScheduleConfig(
        id="due-1", name="due-now", schedule_type=ScheduleType.CUSTOM, interval_seconds=3600,
        scan_paths=[str(scan_dir)],
    )
    due_schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=1)  # already due
    save_schedules([due_schedule], schedules_path)

    engine = make_engine(tmp_path / "scheduler_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    events = []
    service = SchedulerService(
        session_factory, schedules_path=schedules_path, on_event=lambda name, data: events.append(name)
    )
    service.tick()

    assert "scan_triggered" in events
    assert "scan_completed" in events

    with session_scope(session_factory) as session:
        scans = list_scans(session)
        assert len(scans) == 1
        assert scans[0].pii_findings >= 1

    reloaded = load_schedules(schedules_path)
    assert reloaded[0].last_run_at is not None
    assert reloaded[0].next_run_at > datetime.now(UTC)


def test_scheduler_service_skips_not_yet_due_schedule(tmp_path):
    schedules_path = tmp_path / "schedules.json"
    future_schedule = ScheduleConfig(id="future-1", name="later", schedule_type=ScheduleType.DAILY, time_of_day="23:59")
    future_schedule.next_run_at = datetime.now(UTC) + timedelta(hours=5)
    save_schedules([future_schedule], schedules_path)

    engine = make_engine(tmp_path / "scheduler_test2.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    events = []
    service = SchedulerService(
        session_factory, schedules_path=schedules_path, on_event=lambda name, data: events.append(name)
    )
    service.tick()

    assert "scan_triggered" not in events


def test_scheduler_service_disabled_schedule_never_fires(tmp_path):
    schedules_path = tmp_path / "schedules.json"
    disabled = ScheduleConfig(
        id="off-1", name="disabled", schedule_type=ScheduleType.CUSTOM, interval_seconds=60, enabled=False,
    )
    disabled.next_run_at = datetime.now(UTC) - timedelta(hours=1)
    save_schedules([disabled], schedules_path)

    engine = make_engine(tmp_path / "scheduler_test3.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    events = []
    service = SchedulerService(
        session_factory, schedules_path=schedules_path, on_event=lambda name, data: events.append(name)
    )
    service.tick()

    assert events == []


def test_scheduler_service_run_forever_stops_cleanly(tmp_path):
    """`stop()` (as called from a SIGTERM handler) must make `run_forever()`
    return promptly rather than blocking for the full poll interval."""
    import threading
    import time

    schedules_path = tmp_path / "schedules.json"
    save_schedules([], schedules_path)

    engine = make_engine(tmp_path / "scheduler_test5.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    events = []
    service = SchedulerService(
        session_factory,
        schedules_path=schedules_path,
        poll_interval_seconds=30,  # deliberately long — stop() must not wait for this
        on_event=lambda name, data: events.append(name),
    )

    thread = threading.Thread(target=service.run_forever, daemon=True)
    started_at = time.monotonic()
    thread.start()
    time.sleep(0.1)  # let the loop enter its first wait()
    service.stop()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert time.monotonic() - started_at < 5
    assert events[0] == "scheduler_started"
    assert events[-1] == "scheduler_stopped"


def test_once_schedule_disables_itself_after_firing(tmp_path):
    schedules_path = tmp_path / "schedules.json"
    scan_dir = tmp_path / "target"
    scan_dir.mkdir()

    schedule = ScheduleConfig(
        id="once-1", name="one-shot", schedule_type=ScheduleType.ONCE,
        run_at=datetime.now(UTC) - timedelta(minutes=1), scan_paths=[str(scan_dir)],
    )
    schedule.next_run_at = schedule.run_at
    save_schedules([schedule], schedules_path)

    engine = make_engine(tmp_path / "scheduler_test4.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    SchedulerService(session_factory, schedules_path=schedules_path).tick()

    reloaded = load_schedules(schedules_path)
    assert reloaded[0].enabled is False
    assert reloaded[0].next_run_at is None
