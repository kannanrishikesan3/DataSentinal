"""Centrally-pushed policy sync (spec section 42) tests. No real network
calls — httpx.MockTransport simulates the backend, matching test_ai.py's
pattern for the OpenRouter client."""

from __future__ import annotations

import json

import httpx
import pytest

from datasentinel_agent.config.scan_config import load_scan_config
from datasentinel_agent.config.settings import Settings
from datasentinel_agent.sync.backend_client import BackendClient, BackendUnavailable
from datasentinel_agent.sync.policy_sync import apply_remote_policies, sync_policies


def _settings(**overrides) -> Settings:
    defaults = {
        "DATASENTINEL_BACKEND_URL": "https://backend.example.com",
        "DATASENTINEL_ENDPOINT_TOKEN": "et_test_token",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_fetch_effective_policies_returns_parsed_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer et_test_token"
        assert request.url.path == "/api/v1/policies/effective"
        return httpx.Response(200, json=[{"name": "p1", "config": {"risk": {"aggregation_category_threshold": 2}}}])

    client = BackendClient("https://backend.example.com", "et_test_token", transport=httpx.MockTransport(handler))
    policies = client.fetch_effective_policies()
    client.close()

    assert policies == [{"name": "p1", "config": {"risk": {"aggregation_category_threshold": 2}}}]


def test_fetch_effective_policies_raises_backend_unavailable_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid API token"})

    client = BackendClient("https://backend.example.com", "bad-token", transport=httpx.MockTransport(handler))
    with pytest.raises(BackendUnavailable):
        client.fetch_effective_policies()
    client.close()


def test_fetch_effective_policies_raises_backend_unavailable_on_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = BackendClient(
        "https://backend.example.com", "et_test_token", max_retries=0, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(BackendUnavailable):
        client.fetch_effective_policies()
    client.close()


def test_apply_remote_policies_overrides_risk_thresholds():
    base = load_scan_config()
    assert base.risk.aggregation_category_threshold != 2

    merged = apply_remote_policies(base, [{"name": "p1", "config": {"risk": {"aggregation_category_threshold": 2}}}])

    assert merged.risk.aggregation_category_threshold == 2
    # The input config is never mutated.
    assert base.risk.aggregation_category_threshold != 2


def test_apply_remote_policies_merges_exclude_paths():
    base = load_scan_config()
    original_count = len(base.exclude_paths.get("linux", []))

    merged = apply_remote_policies(base, [{"config": {"exclude_paths": {"linux": ["/extra/quarantine"]}}}])

    assert "/extra/quarantine" in merged.exclude_paths["linux"]
    assert len(merged.exclude_paths["linux"]) == original_count + 1


def test_apply_remote_policies_overrides_a_named_profile():
    base = load_scan_config()
    assert base.scan.profiles["standard"].scan_archives is False

    merged = apply_remote_policies(base, [{"config": {"profiles": {"standard": {"scan_archives": True}}}}])

    assert merged.scan.profiles["standard"].scan_archives is True
    # Other profiles are untouched.
    assert merged.scan.profiles["quick"].scan_archives is False


def test_apply_remote_policies_ignores_unknown_fields_and_profiles():
    base = load_scan_config()
    merged = apply_remote_policies(
        base,
        [{"config": {"risk": {"not_a_real_field": 123}, "profiles": {"nonexistent": {"max_depth": 1}}}}],
    )
    assert merged.risk == base.risk
    assert "nonexistent" not in merged.scan.profiles


def test_apply_remote_policies_skips_a_malformed_policy_without_raising():
    base = load_scan_config()
    merged = apply_remote_policies(base, ["not-a-dict", {"config": "not-a-dict-either"}, {"config": None}])
    assert merged.risk == base.risk


def test_sync_policies_returns_local_config_when_backend_not_configured():
    settings = Settings(_env_file=None)
    assert settings.backend_url is None and settings.endpoint_token is None
    config = sync_policies(settings)
    assert config == load_scan_config()


def test_sync_policies_falls_back_to_local_config_when_backend_unreachable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    import datasentinel_agent.sync.policy_sync as policy_sync_module

    class _UnreachableClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def fetch_effective_policies(self):
            raise BackendUnavailable("simulated outage")

    monkeypatch.setattr(policy_sync_module, "BackendClient", _UnreachableClient)

    settings = _settings()
    config = sync_policies(settings)
    assert config == load_scan_config()


def test_sync_policies_applies_fetched_policies(monkeypatch):
    import datasentinel_agent.sync.policy_sync as policy_sync_module

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def fetch_effective_policies(self):
            return [{"config": {"risk": {"aggregation_category_threshold": 2}}}]

    monkeypatch.setattr(policy_sync_module, "BackendClient", _FakeClient)

    config = sync_policies(_settings())
    assert config.risk.aggregation_category_threshold == 2
