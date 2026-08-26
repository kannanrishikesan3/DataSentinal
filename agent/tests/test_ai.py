"""Phase 11 tests. No real network calls — httpx.MockTransport simulates
OpenRouter so we can exercise success, failure, timeout, and malformed-
response paths deterministically."""

import json

import httpx
import pytest

from datasentinel_agent.ai.openrouter_client import OpenRouterClient
from datasentinel_agent.ai.redaction_context import build_redacted_context
from datasentinel_agent.ai.service import AIReviewService
from datasentinel_agent.config.settings import Settings
from datasentinel_agent.core.enums import DetectionMethod, Severity
from datasentinel_agent.core.schema import Finding
from datetime import datetime, timezone


def _openrouter_response(is_pii=True, category="email", confidence=0.8, severity="low", reason="looks like an email"):
    body = {"is_pii": is_pii, "category": category, "confidence": confidence, "severity": severity, "reason": reason}
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(body)}}]})


def test_build_redacted_context_masks_candidate_and_other_spans():
    text = "Contact John Doe at john.doe@example.com or 555-1234 for details."
    context = build_redacted_context(
        text, candidate_start=13, candidate_end=33, category_placeholder="CANDIDATE:email",
        other_spans=[(0, 8, "CANDIDATE:person")],
    )
    assert "john.doe@example.com" not in context
    assert "John Doe" not in context
    assert "[CANDIDATE:email]" in context


def test_classify_success_returns_parsed_classification():
    def handler(request):
        return _openrouter_response()

    client = OpenRouterClient("fake-key", "fake-model", transport=httpx.MockTransport(handler), min_interval_seconds=0)
    result = client.classify("Category: email\nRedacted evidence: jo***@example.com")
    assert result is not None
    assert result.is_pii is True
    assert result.category == "email"
    client.close()


def test_classify_returns_none_on_http_error_never_raises():
    def handler(request):
        return httpx.Response(500)

    client = OpenRouterClient("fake-key", "fake-model", transport=httpx.MockTransport(handler), min_interval_seconds=0, max_retries=1)
    result = client.classify("anything")
    assert result is None
    client.close()


def test_classify_returns_none_on_malformed_json_never_raises():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "not valid json!!"}}]})

    client = OpenRouterClient("fake-key", "fake-model", transport=httpx.MockTransport(handler), min_interval_seconds=0, max_retries=0)
    assert client.classify("anything") is None
    client.close()


def test_classify_retries_then_succeeds():
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if calls["count"] < 2:
            return httpx.Response(503)
        return _openrouter_response()

    client = OpenRouterClient("fake-key", "fake-model", transport=httpx.MockTransport(handler), min_interval_seconds=0, max_retries=2)
    result = client.classify("anything")
    assert result is not None
    assert calls["count"] == 2
    client.close()


def test_classify_never_raises_on_connect_error():
    def handler(request):
        raise httpx.ConnectError("simulated network failure", request=request)

    client = OpenRouterClient("fake-key", "fake-model", transport=httpx.MockTransport(handler), min_interval_seconds=0, max_retries=0)
    assert client.classify("anything") is None
    client.close()


def test_classify_never_raises_on_timeout():
    def handler(request):
        raise httpx.TimeoutException("simulated timeout", request=request)

    client = OpenRouterClient(
        "fake-key", "fake-model", transport=httpx.MockTransport(handler), min_interval_seconds=0, max_retries=0
    )
    assert client.classify("anything") is None
    client.close()


def test_ai_review_service_leaves_finding_unchanged_on_timeout():
    def handler(request):
        raise httpx.TimeoutException("simulated timeout", request=request)

    client = OpenRouterClient("k", "m", transport=httpx.MockTransport(handler), min_interval_seconds=0, max_retries=0)
    service = AIReviewService(Settings(_env_file=None), client=client, threshold=0.7)
    finding = _finding(confidence=0.4)
    result = service.review_finding(finding)
    assert result.confidence == 0.4  # scan continues normally despite the AI timeout
    service.close()


def _finding(confidence=0.4):
    return Finding(
        finding_id="f1", scan_id="scan-1", file_path="/home/user/file.txt",
        category="email", severity=Severity.LOW, confidence=confidence,
        detection_method=DetectionMethod.REGEX, redacted_evidence="jo***@example.com",
        detected_at=datetime.now(timezone.utc),
    )


def test_ai_review_service_disabled_without_configured_client():
    settings = Settings(_env_file=None)  # AI_ENABLED defaults false
    service = AIReviewService(settings)
    assert service.enabled is False
    finding = _finding()
    assert service.review_finding(finding) == finding


def test_ai_review_service_skips_high_confidence_findings():
    def handler(request):
        raise AssertionError("should never be called for a high-confidence finding")

    client = OpenRouterClient("k", "m", transport=httpx.MockTransport(handler), min_interval_seconds=0)
    service = AIReviewService(Settings(_env_file=None), client=client, threshold=0.7)
    finding = _finding(confidence=0.95)
    result = service.review_finding(finding)
    assert result.confidence == 0.95
    service.close()


def test_ai_review_service_blends_confidence_for_low_confidence_finding():
    def handler(request):
        return _openrouter_response(confidence=1.0)

    client = OpenRouterClient("k", "m", transport=httpx.MockTransport(handler), min_interval_seconds=0)
    service = AIReviewService(Settings(_env_file=None), client=client, threshold=0.7)
    finding = _finding(confidence=0.4)
    result = service.review_finding(finding)
    assert result.confidence == pytest.approx(0.7, abs=0.01)  # (0.4 + 1.0) / 2
    service.close()


def test_ai_review_service_leaves_finding_unchanged_when_provider_fails():
    def handler(request):
        return httpx.Response(500)

    client = OpenRouterClient("k", "m", transport=httpx.MockTransport(handler), min_interval_seconds=0, max_retries=0)
    service = AIReviewService(Settings(_env_file=None), client=client, threshold=0.7)
    finding = _finding(confidence=0.4)
    result = service.review_finding(finding)
    assert result.confidence == 0.4  # unchanged — AI failure never blocks/alters the scan
    service.close()


def test_ai_review_service_survives_unexpected_exception_type_from_client(monkeypatch):
    # The OpenRouter client's own `classify()` already catches every
    # exception type it knows about (httpx errors, malformed JSON, etc.) and
    # returns None. This proves the call *site* in AIReviewService also
    # tolerates an exception type entirely outside that — e.g. a client bug
    # — that isn't part of the client's normal except-tuple and would
    # otherwise propagate straight out of review_finding and abort the scan.
    client = OpenRouterClient("k", "m", transport=httpx.MockTransport(lambda r: _openrouter_response()), min_interval_seconds=0)

    def _boom(redacted_context):
        raise RuntimeError("simulated bug unrelated to network/parsing failures")

    monkeypatch.setattr(client, "classify", _boom)

    service = AIReviewService(Settings(_env_file=None), client=client, threshold=0.7)
    finding = _finding(confidence=0.4)
    result = service.review_finding(finding)

    assert result == finding  # completely unchanged, and no exception propagated
    service.close()


def test_ai_never_receives_raw_value_only_redacted_evidence():
    captured = {}

    def handler(request):
        captured["body"] = request.content.decode()
        return _openrouter_response()

    client = OpenRouterClient("k", "m", transport=httpx.MockTransport(handler), min_interval_seconds=0)
    service = AIReviewService(Settings(_env_file=None), client=client, threshold=0.7)
    finding = _finding(confidence=0.4)
    service.review_finding(finding)

    assert "jo***@example.com" in captured["body"]  # redacted evidence only
    service.close()
