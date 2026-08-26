"""`datasentinel enroll` — self-registration using a reusable enrollment
token (spec sections 7-13), the CLI counterpart to an admin manually
registering an endpoint from the dashboard. No real network calls —
httpx.MockTransport simulates the backend, matching test_ai.py's pattern.
"""

from __future__ import annotations

import json

import httpx
import pytest
from click.testing import CliRunner

from datasentinel_agent.cli.main import cli


def _mock_success(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/api/v1/endpoints/enroll"
    body = json.loads(request.content)
    assert body["enrollment_token"] == "dset_fake-token"
    response = httpx.Response(
        201,
        json={
            "endpoint": {
                "id": "11111111-1111-1111-1111-111111111111", "name": body["name"], "hostname": body["hostname"],
                "os": body["os"], "os_version": None, "agent_version": None, "status": "active",
                "last_seen_at": None, "registered_at": "2026-01-01T00:00:00", "last_scan": None, "risk_score": 0,
            },
            "api_token": "dsat_11111111-1111-1111-1111-111111111111_fakesecret",
        },
        request=request,
    )
    return response


@pytest.fixture(autouse=True)
def _patch_httpx_post(monkeypatch):
    """`enroll` calls the module-level `httpx.post` directly (a one-shot CLI
    call, not a long-lived client worth injecting a transport into) — patch
    it globally for the duration of each test in this file."""
    handler = {"fn": _mock_success}

    def fake_post(url, *, json=None, timeout=None):
        request = httpx.Request("POST", url, json=json)
        return handler["fn"](request)

    monkeypatch.setattr(httpx, "post", fake_post)
    yield handler


def test_enroll_writes_credentials_to_the_env_file(tmp_path):
    env_file = tmp_path / ".env"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "enroll", "--server-url", "http://backend.example.com", "--token", "dset_fake-token",
            "--hostname", "test-laptop", "--os", "linux", "--env-file", str(env_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Enrolled as endpoint" in result.output
    assert "dsat_" not in result.output  # the credential itself is never echoed to the terminal

    content = env_file.read_text()
    assert "DATASENTINEL_BACKEND_URL=http://backend.example.com" in content
    assert "DATASENTINEL_ENDPOINT_TOKEN=dsat_11111111" in content


def test_enroll_preserves_unrelated_existing_env_lines(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("AI_ENABLED=false\nDATASENTINEL_LOG_LEVEL=DEBUG\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "enroll", "--server-url", "http://backend.example.com", "--token", "dset_fake-token",
            "--hostname", "test-laptop", "--os", "linux", "--env-file", str(env_file),
        ],
    )
    assert result.exit_code == 0, result.output

    content = env_file.read_text()
    assert "AI_ENABLED=false" in content
    assert "DATASENTINEL_LOG_LEVEL=DEBUG" in content
    assert "DATASENTINEL_BACKEND_URL=http://backend.example.com" in content


def test_enroll_overwrites_a_stale_previous_credential_not_duplicates_it(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DATASENTINEL_BACKEND_URL=http://old.example.com\nDATASENTINEL_ENDPOINT_TOKEN=dsat_stale\n")

    runner = CliRunner()
    runner.invoke(
        cli,
        [
            "enroll", "--server-url", "http://backend.example.com", "--token", "dset_fake-token",
            "--hostname", "test-laptop", "--os", "linux", "--env-file", str(env_file),
        ],
    )

    content = env_file.read_text()
    assert content.count("DATASENTINEL_BACKEND_URL=") == 1
    assert content.count("DATASENTINEL_ENDPOINT_TOKEN=") == 1
    assert "old.example.com" not in content
    assert "dsat_stale" not in content


def test_enroll_defaults_hostname_to_the_real_machine_hostname(tmp_path, monkeypatch):
    monkeypatch.setattr("socket.gethostname", lambda: "auto-detected-host")
    env_file = tmp_path / ".env"
    runner = CliRunner()
    result = runner.invoke(
        cli, ["enroll", "--server-url", "http://backend.example.com", "--token", "dset_fake-token", "--env-file", str(env_file)]
    )
    assert result.exit_code == 0, result.output
    assert "auto-detected-host" in result.output


def test_enroll_auto_detects_macos_instead_of_defaulting_to_linux(tmp_path, monkeypatch):
    # Regression test for Phase 2 (macOS support): the old binary
    # `platform.system() == "Windows"` ternary this replaced would have
    # silently misreported a real Mac as "linux".
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    env_file = tmp_path / ".env"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "enroll", "--server-url", "http://backend.example.com", "--token", "dset_fake-token",
            "--hostname", "test-mac", "--env-file", str(env_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "(macos)" in result.output


def test_enroll_reports_a_clean_error_on_rejection(tmp_path, _patch_httpx_post):
    def rejected(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "Enrollment token is expired"}, request=request)

    _patch_httpx_post["fn"] = rejected

    env_file = tmp_path / ".env"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "enroll", "--server-url", "http://backend.example.com", "--token", "dset_fake-token",
            "--hostname", "test-laptop", "--os", "linux", "--env-file", str(env_file),
        ],
    )
    assert result.exit_code != 0
    assert "expired" in result.output
    assert not env_file.exists()  # a rejected enrollment must never write a (nonexistent) credential


def test_enroll_reports_a_clean_error_when_server_unreachable(tmp_path, monkeypatch):
    def unreachable(url, *, json=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", unreachable)

    env_file = tmp_path / ".env"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "enroll", "--server-url", "http://backend.example.com", "--token", "dset_fake-token",
            "--hostname", "test-laptop", "--os", "linux", "--env-file", str(env_file),
        ],
    )
    assert result.exit_code != 0
    assert "Could not reach" in result.output
    assert not env_file.exists()
