"""Scan report upload (spec sections 12/39/53) tests. No real network
calls — httpx.MockTransport simulates the backend."""

from __future__ import annotations

import json

import httpx

from datasentinel_agent.config.scan_config import load_scan_config
from datasentinel_agent.config.settings import Settings
from datasentinel_agent.core.enums import ScanStatus
from datasentinel_agent.core.pipeline import ScanOptions, run_scan
from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory, session_scope
from datasentinel_agent.storage.repository import get_scan
from datasentinel_agent.sync.backend_client import BackendClient, BackendUnavailable
from datasentinel_agent.sync.scan_uploader import build_scan_report_payload, upload_scan


def _settings(**overrides) -> Settings:
    defaults = {
        "DATASENTINEL_BACKEND_URL": "https://backend.example.com",
        "DATASENTINEL_ENDPOINT_TOKEN": "et_test_token",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _run_local_scan(tmp_path):
    (tmp_path / "notes.txt").write_text("Email: still.works@example.com\n")
    engine = make_engine(tmp_path / "agent_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)
    options = ScanOptions(profile="standard", paths=[tmp_path], use_presidio=False)
    summary = run_scan(options, session_factory)
    with session_scope(session_factory) as session:
        scan_record = get_scan(session, summary.scan_id)
        return summary, list(scan_record.files), list(scan_record.findings), list(scan_record.errors), scan_record


def test_build_scan_report_payload_matches_backend_shape(tmp_path):
    _, files, findings, errors, scan_record = _run_local_scan(tmp_path)
    payload = build_scan_report_payload(scan_record, files, findings, errors)

    assert payload["profile"] == "standard"
    assert payload["status"] == "completed"
    assert payload["pii_findings"] >= 1
    assert isinstance(payload["files"], list)
    assert isinstance(payload["findings"], list)
    assert isinstance(payload["errors"], list)
    if payload["findings"]:
        finding_payload = payload["findings"][0]
        assert set(finding_payload) == {
            "finding_id", "file_path", "file_hash", "category", "is_secret", "severity",
            "confidence", "occurrence_count", "page_number", "line_number", "sheet_name",
            "detection_method", "redacted_evidence", "detected_at",
        }


def test_upload_scan_returns_false_when_backend_not_configured(tmp_path):
    _, files, findings, errors, scan_record = _run_local_scan(tmp_path)
    settings = Settings(_env_file=None)
    assert upload_scan(settings, scan_record, files, findings, errors) is False


def test_upload_scan_posts_payload_and_returns_true_on_success(tmp_path):
    _, files, findings, errors, scan_record = _run_local_scan(tmp_path)

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "some-uuid"})

    import datasentinel_agent.sync.scan_uploader as scan_uploader_module

    class _Client(BackendClient):
        def __init__(self, base_url, token, **kwargs):
            super().__init__(base_url, token, transport=httpx.MockTransport(handler))

    orig = scan_uploader_module.BackendClient
    scan_uploader_module.BackendClient = _Client
    try:
        result = upload_scan(_settings(), scan_record, files, findings, errors)
    finally:
        scan_uploader_module.BackendClient = orig

    assert result is True
    assert captured["auth"] == "Bearer et_test_token"
    assert captured["body"]["profile"] == "standard"


def test_upload_scan_returns_false_when_backend_unreachable(tmp_path, monkeypatch):
    _, files, findings, errors, scan_record = _run_local_scan(tmp_path)

    import datasentinel_agent.sync.scan_uploader as scan_uploader_module

    class _UnreachableClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def submit_scan_report(self, payload):
            raise BackendUnavailable("simulated outage")

    monkeypatch.setattr(scan_uploader_module, "BackendClient", _UnreachableClient)

    result = upload_scan(_settings(), scan_record, files, findings, errors)
    assert result is False


def test_run_scan_attempts_upload_when_backend_configured(tmp_path, monkeypatch):
    """The pipeline itself must call the uploader once a scan completes,
    when (and only when) the backend is configured — without blocking or
    failing the scan if that upload fails."""
    import datasentinel_agent.core.pipeline as pipeline_module

    calls = []

    def fake_upload_scan(settings, scan_record, files, findings, errors):
        calls.append(scan_record.scan_id)
        return True

    monkeypatch.setattr(pipeline_module, "upload_scan", fake_upload_scan)
    monkeypatch.setattr(pipeline_module, "get_settings", lambda: _settings())

    (tmp_path / "notes.txt").write_text("nothing sensitive\n")
    engine = make_engine(tmp_path / "agent_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)
    options = ScanOptions(profile="standard", paths=[tmp_path], use_presidio=False)
    summary = run_scan(options, session_factory)

    assert summary.status == ScanStatus.COMPLETED
    assert calls == [summary.scan_id]


def test_run_scan_completes_even_when_upload_raises_unexpectedly(tmp_path, monkeypatch):
    """Defense in depth: even if the uploader itself had a bug, a scan that
    already succeeded must still be reported as successful, never aborted
    by a post-hoc upload failure."""
    import datasentinel_agent.core.pipeline as pipeline_module

    def broken_upload_scan(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(pipeline_module, "upload_scan", broken_upload_scan)

    (tmp_path / "notes.txt").write_text("nothing sensitive\n")
    engine = make_engine(tmp_path / "agent_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)
    options = ScanOptions(profile="standard", paths=[tmp_path], use_presidio=False)

    summary = run_scan(options, session_factory)
    assert summary.status == ScanStatus.COMPLETED
