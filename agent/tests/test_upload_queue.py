"""Offline upload queue (spec section 53) tests: a failed scan upload is
queued and retried on a later scheduler tick, a stale entry expires per the
configured retention, and a successful retry (or a successful upload the
first time around) dequeues it."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from datasentinel_agent.config.settings import Settings
from datasentinel_agent.core.enums import ScanStatus
from datasentinel_agent.core.pipeline import ScanOptions, run_scan
from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory
from datasentinel_agent.sync.scan_uploader import retry_pending_uploads
from datasentinel_agent.sync.upload_queue import PendingUpload, dequeue, enqueue, load_pending, prune_expired


def _settings(**overrides) -> Settings:
    defaults = {
        "DATASENTINEL_BACKEND_URL": "https://backend.example.com",
        "DATASENTINEL_ENDPOINT_TOKEN": "et_test_token",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _run_local_scan(tmp_path, name="notes.txt"):
    (tmp_path / name).write_text("Email: still.works@example.com\n")
    engine = make_engine(tmp_path / "agent_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)
    options = ScanOptions(profile="standard", paths=[tmp_path], use_presidio=False)
    summary = run_scan(options, session_factory)
    return summary, session_factory


def test_enqueue_then_dequeue_round_trips(tmp_path):
    path = tmp_path / "pending.json"
    enqueue("scan-1", path)

    pending = load_pending(path)
    assert len(pending) == 1
    assert pending[0].scan_id == "scan-1"
    assert pending[0].attempts == 1

    dequeue("scan-1", path)
    assert load_pending(path) == []


def test_enqueue_twice_bumps_attempts_not_duplicates(tmp_path):
    path = tmp_path / "pending.json"
    enqueue("scan-1", path)
    enqueue("scan-1", path)

    pending = load_pending(path)
    assert len(pending) == 1
    assert pending[0].attempts == 2


def test_prune_expired_drops_old_entries_and_keeps_recent(tmp_path):
    path = tmp_path / "pending.json"
    now = datetime.now(timezone.utc)
    old = PendingUpload(scan_id="old-scan", first_failed_at=now - timedelta(days=10), last_attempt_at=now, attempts=3)
    recent = PendingUpload(scan_id="recent-scan", first_failed_at=now - timedelta(days=1), last_attempt_at=now, attempts=1)
    from datasentinel_agent.sync.upload_queue import save_pending

    save_pending([old, recent], path)

    kept = prune_expired(retention_days=7, path=path)
    assert [p.scan_id for p in kept] == ["recent-scan"]
    assert [p.scan_id for p in load_pending(path)] == ["recent-scan"]


def test_run_scan_queues_a_failed_upload(tmp_path, monkeypatch):
    import datasentinel_agent.core.pipeline as pipeline_module

    pending_path = tmp_path / "pending.json"
    monkeypatch.setattr(pipeline_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(pipeline_module, "enqueue", lambda scan_id: enqueue(scan_id, pending_path))
    monkeypatch.setattr(pipeline_module, "dequeue", lambda scan_id: dequeue(scan_id, pending_path))
    monkeypatch.setattr(pipeline_module, "upload_scan", lambda *a, **kw: False)

    summary, _ = _run_local_scan(tmp_path)

    assert summary.status == ScanStatus.COMPLETED
    pending = load_pending(pending_path)
    assert [p.scan_id for p in pending] == [summary.scan_id]


def test_run_scan_does_not_queue_a_successful_upload(tmp_path, monkeypatch):
    import datasentinel_agent.core.pipeline as pipeline_module

    pending_path = tmp_path / "pending.json"
    monkeypatch.setattr(pipeline_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(pipeline_module, "enqueue", lambda scan_id: enqueue(scan_id, pending_path))
    monkeypatch.setattr(pipeline_module, "dequeue", lambda scan_id: dequeue(scan_id, pending_path))
    monkeypatch.setattr(pipeline_module, "upload_scan", lambda *a, **kw: True)

    _run_local_scan(tmp_path)

    assert load_pending(pending_path) == []


def test_retry_pending_uploads_dequeues_on_success(tmp_path, monkeypatch):
    summary, session_factory = _run_local_scan(tmp_path)
    pending_path = tmp_path / "pending.json"
    enqueue(summary.scan_id, pending_path)

    import datasentinel_agent.sync.scan_uploader as scan_uploader_module

    monkeypatch.setattr(scan_uploader_module, "upload_scan", lambda *a, **kw: True)

    uploaded = retry_pending_uploads(_settings(), session_factory, retention_days=7, path=pending_path)

    assert uploaded == 1
    assert load_pending(pending_path) == []


def test_retry_pending_uploads_keeps_queued_on_repeated_failure(tmp_path, monkeypatch):
    summary, session_factory = _run_local_scan(tmp_path)
    pending_path = tmp_path / "pending.json"
    enqueue(summary.scan_id, pending_path)

    import datasentinel_agent.sync.scan_uploader as scan_uploader_module

    monkeypatch.setattr(scan_uploader_module, "upload_scan", lambda *a, **kw: False)

    uploaded = retry_pending_uploads(_settings(), session_factory, retention_days=7, path=pending_path)

    assert uploaded == 0
    pending = load_pending(pending_path)
    assert len(pending) == 1
    assert pending[0].attempts == 2  # bumped by the failed retry


def test_retry_pending_uploads_drops_a_scan_missing_locally(tmp_path):
    _, session_factory = _run_local_scan(tmp_path)
    pending_path = tmp_path / "pending.json"
    enqueue("scan-that-was-never-actually-stored", pending_path)

    uploaded = retry_pending_uploads(_settings(), session_factory, retention_days=7, path=pending_path)

    assert uploaded == 0
    assert load_pending(pending_path) == []


def test_retry_pending_uploads_noop_when_backend_not_configured(tmp_path):
    summary, session_factory = _run_local_scan(tmp_path)
    pending_path = tmp_path / "pending.json"
    enqueue(summary.scan_id, pending_path)

    settings = Settings(_env_file=None)
    uploaded = retry_pending_uploads(settings, session_factory, retention_days=7, path=pending_path)

    assert uploaded == 0
    assert len(load_pending(pending_path)) == 1  # left untouched, not dropped


def test_scheduler_tick_retries_pending_uploads(tmp_path, monkeypatch):
    from datasentinel_agent.scheduler.service import SchedulerService

    summary, session_factory = _run_local_scan(tmp_path)
    pending_path = tmp_path / "pending.json"
    enqueue(summary.scan_id, pending_path)

    import datasentinel_agent.scheduler.service as scheduler_module

    monkeypatch.setattr(scheduler_module, "get_settings", lambda: _settings())

    called = {}

    def fake_retry(settings, session_factory_arg, retention_days):
        called["settings"] = settings
        called["retention_days"] = retention_days
        return 1

    monkeypatch.setattr(scheduler_module, "retry_pending_uploads", fake_retry)

    events = []
    scheduler = SchedulerService(session_factory, schedules_path=tmp_path / "schedules.json", on_event=lambda n, d: events.append((n, d)))
    scheduler.tick()

    assert called["retention_days"] == 7
    assert ("pending_uploads_retried", {"uploaded": 1}) in events


def test_scheduler_tick_survives_a_retry_failure(tmp_path, monkeypatch):
    from datasentinel_agent.scheduler.service import SchedulerService

    _, session_factory = _run_local_scan(tmp_path)

    import datasentinel_agent.scheduler.service as scheduler_module

    monkeypatch.setattr(scheduler_module, "get_settings", lambda: _settings())

    def broken_retry(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(scheduler_module, "retry_pending_uploads", broken_retry)

    events = []
    scheduler = SchedulerService(session_factory, schedules_path=tmp_path / "schedules.json", on_event=lambda n, d: events.append((n, d)))
    scheduler.tick()  # must not raise

    assert any(name == "pending_upload_retry_failed" for name, _ in events)
