"""Phase 17 tests: the logging module never lets a raw sensitive value reach
formatted output, and pipeline logging doesn't crash real scans."""

import io
import logging

from datasentinel_agent.logging.redaction_filter import RedactionFilter, redact
from datasentinel_agent.logging.setup import JsonFormatter


def test_redact_masks_email():
    assert "leak@example.com" not in redact("User leak@example.com logged in")
    assert "[REDACTED_EMAIL]" in redact("User leak@example.com logged in")


def test_redact_masks_ssn_and_card_like_numbers():
    assert "123-45-6789" not in redact("SSN found: 123-45-6789")
    assert "4532015112830366" not in redact("Card: 4532015112830366")


def test_redact_masks_aws_key():
    assert "AKIAABCD1234EFGH5678" not in redact("key=AKIAABCD1234EFGH5678")


def test_redact_masks_password_assignment():
    result = redact('password = "hunter2ExtraLong"')
    assert "hunter2ExtraLong" not in result
    assert "[REDACTED]" in result


def test_redact_leaves_ordinary_text_unchanged():
    text = "Scan completed: 42 files scanned, 3 findings"
    assert redact(text) == text


def test_redaction_filter_rewrites_log_record():
    logger = logging.getLogger("test.redaction")
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactionFilter())
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False

    logger.info("Contact: leaked@example.com")
    handler.flush()

    output = stream.getvalue()
    assert "leaked@example.com" not in output
    assert "[REDACTED_EMAIL]" in output

    logger.removeHandler(handler)


def test_json_formatter_produces_valid_json():
    import json

    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="scan complete", args=(), exc_info=None,
    )
    formatted = JsonFormatter().format(record)
    parsed = json.loads(formatted)
    assert parsed["message"] == "scan complete"
    assert parsed["level"] == "INFO"


def test_pipeline_logging_never_leaks_finding_evidence(tmp_path, caplog):
    """The pipeline's own log calls must never include a finding's raw or
    even redacted evidence — only counts and paths."""
    import logging as _logging

    from datasentinel_agent.core.pipeline import ScanOptions, run_scan
    from datasentinel_agent.storage.database import init_db, make_engine, make_session_factory

    (tmp_path / "notes.txt").write_text("Email: pipeline.log.test@example.com\n")

    engine = make_engine(tmp_path / "log_test.db")
    init_db(engine)
    session_factory = make_session_factory(engine)

    with caplog.at_level(_logging.INFO, logger="datasentinel_agent.pipeline"):
        run_scan(ScanOptions(profile="standard", paths=[tmp_path], use_presidio=False), session_factory)

    for record in caplog.records:
        assert "pipeline.log.test@example.com" not in record.getMessage()
