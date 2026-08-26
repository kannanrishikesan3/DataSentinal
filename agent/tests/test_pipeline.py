"""End-to-end pipeline integration test: discovery -> parsing -> detection ->
risk -> storage, all wired together against a real temp directory tree."""

import sys

import pytest

from datasentinel_agent.core.enums import ScanStatus
from datasentinel_agent.core.pipeline import ScanOptions, run_scan
from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory, session_scope
from datasentinel_agent.storage.repository import list_findings


def test_full_scan_pipeline_end_to_end(tmp_path):
    (tmp_path / "employees.csv").write_text(
        "name,email,ssn\nJohn Synthetic,john.synthetic@example.com,123-45-6789\n"
    )
    (tmp_path / "config.log").write_text("aws_access_key_id = AKIAABCD1234EFGH5678\n")
    (tmp_path / "notes.txt").write_text("Nothing sensitive here, just some notes.\n")

    engine = make_engine(tmp_path / "agent_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    events = []
    options = ScanOptions(profile="standard", paths=[tmp_path], use_presidio=False)
    summary = run_scan(options, session_factory, on_progress=lambda name, data: events.append(name))

    assert summary.status == ScanStatus.COMPLETED
    assert summary.files_discovered == 3
    assert summary.files_scanned == 3
    assert summary.pii_findings >= 1
    assert summary.secret_findings >= 1
    assert "scan_completed" in events

    with session_scope(session_factory) as session:
        findings = list_findings(session, scan_id=summary.scan_id)
        categories = {f.category for f in findings}
        assert "email" in categories or "ssn" in categories
        assert "aws_credentials" in categories
        # No raw secret value ever made it into storage.
        assert all("AKIAABCD1234EFGH5678" not in f.redacted_evidence for f in findings)


def test_scan_pipeline_survives_a_corrupted_file(tmp_path):
    (tmp_path / "broken.json").write_text("{not valid json")
    (tmp_path / "good.txt").write_text("Email: still.works@example.com\n")

    engine = make_engine(tmp_path / "agent_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    options = ScanOptions(profile="standard", paths=[tmp_path], use_presidio=False)
    summary = run_scan(options, session_factory)

    assert summary.status == ScanStatus.COMPLETED
    assert summary.files_skipped >= 1  # the broken.json parse failure
    assert summary.pii_findings >= 1  # good.txt was still scanned

    # The parse error must be persisted, not just reflected in the returned
    # summary object — a later `datasentinel report` or backend sync reads
    # it from the database.
    from datasentinel_agent.storage.repository import list_scan_errors

    with session_scope(session_factory) as session:
        errors = list_scan_errors(session, summary.scan_id)
        assert any(e.error_type == "parse_error" for e in errors)


@pytest.mark.skipif(sys.platform == "win32", reason="RLIMIT_AS is POSIX-only")
def test_run_scan_applies_process_memory_limit(tmp_path, monkeypatch):
    # A best-effort process-wide memory cap must be set once at the start of
    # a scan (never per-file). Monkeypatch `resource.setrlimit` rather than
    # actually lowering this test process's own memory limit, which could
    # break the test run itself.
    import resource

    from datasentinel_agent.config.scan_config import load_scan_config

    (tmp_path / "notes.txt").write_text("nothing sensitive\n")

    calls = []
    monkeypatch.setattr(
        resource, "setrlimit", lambda which, limits: calls.append((which, limits))
    )

    engine = make_engine(tmp_path / "agent_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    options = ScanOptions(profile="standard", paths=[tmp_path], use_presidio=False)
    run_scan(options, session_factory)

    expected_mb = load_scan_config().scan.max_memory_mb
    expected_bytes = expected_mb * 1024 * 1024
    assert calls == [(resource.RLIMIT_AS, (expected_bytes, expected_bytes))]


def test_scan_completes_when_ai_review_raises_an_unexpected_exception(tmp_path, monkeypatch):
    # Spec: "If OpenRouter fails, scanning must continue normally." This
    # exercises a failure mode entirely outside what OpenRouterClient's own
    # except-tuple handles (a client bug, not a network/parsing failure) to
    # prove the scan loop itself can never be aborted by the AI layer.
    from datasentinel_agent.ai.openrouter_client import OpenRouterClient
    from datasentinel_agent.config.settings import Settings

    def _boom(self, redacted_context):
        raise RuntimeError("simulated bug unrelated to network/parsing failures")

    monkeypatch.setattr(OpenRouterClient, "classify", _boom)

    # Low-confidence phone-like number (a competing keyword drags it below
    # the AI review threshold) so the pipeline actually calls into AI review.
    (tmp_path / "notes.txt").write_text("Reference number: 5551234567\n")

    engine = make_engine(tmp_path / "agent_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    settings = Settings(
        _env_file=None, AI_ENABLED=True, OPENROUTER_API_KEY="fake-key", OPENROUTER_MODEL="fake-model"
    )
    options = ScanOptions(profile="standard", paths=[tmp_path], use_presidio=False, use_ai=True)
    summary = run_scan(options, session_factory, settings=settings)

    assert summary.status == ScanStatus.COMPLETED
    assert summary.files_scanned == 1
    assert summary.pii_findings >= 1


def test_apply_memory_limit_never_raises_when_setrlimit_fails(monkeypatch):
    from datasentinel_agent.core.pipeline import _apply_memory_limit

    if sys.platform != "win32":
        import resource

        def _boom(which, limits):
            raise OSError("simulated: limit already lower than requested")

        monkeypatch.setattr(resource, "setrlimit", _boom)

    _apply_memory_limit(2048)  # must not raise regardless of platform
