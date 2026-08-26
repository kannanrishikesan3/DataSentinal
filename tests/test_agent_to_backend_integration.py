"""Cross-component integration test: a real agent scan (discovery -> PII
detection -> risk scoring -> local storage) produces a scan report which is
submitted to a real in-process backend API, then read back through the
dashboard query endpoint.

Nothing is mocked on either side:

- The agent side runs `datasentinel_agent.core.pipeline.run_scan` against a
  real temp directory, exactly the way the agent's own CLI does internally,
  and persists to a real (temp-file) SQLite database via the agent's own
  storage layer.
- The backend side is a real FastAPI app (`datasentinel_backend.main.app`)
  driven through `TestClient`, backed by a throwaway in-memory SQLite
  database (the same pattern backend/tests/conftest.py uses).

Requires both `datasentinel_agent` and `datasentinel_backend` importable in
the same environment. See tests/README.md for how to set that up.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from datasentinel_agent.core.pipeline import ScanOptions, run_scan
from datasentinel_agent.storage.database import (
    init_db as init_agent_db,
    make_engine as make_agent_engine,
    make_session_factory as make_agent_session_factory,
    session_scope,
)
from datasentinel_agent.storage.repository import get_scan, list_findings

from datasentinel_backend.core.config import get_settings
from datasentinel_backend.core.database import get_db, init_db as init_backend_db
from datasentinel_backend.main import app
from datasentinel_backend.models.models import Organization, User
from datasentinel_backend.security.passwords import hash_password

SYNTHETIC_EMAIL = "jane.synthetic@example.com"


def _finding_to_backend_payload(finding) -> dict:
    """Map an agent FindingORM row onto the backend's `FindingIn` schema
    (api/v1/schemas.py). The field names/types are identical by design (see
    agent/datasentinel_agent/core/schema.py's `Finding` docstring: "the
    backend's ingestion API mirrors their shape") -- this is the one place
    that assumption gets exercised end to end instead of just assumed.
    """
    return {
        "finding_id": finding.finding_id,
        "file_path": finding.file_path,
        "file_hash": finding.file_hash,
        "category": finding.category,
        "is_secret": finding.is_secret,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "occurrence_count": finding.occurrence_count,
        "page_number": finding.page_number,
        "line_number": finding.line_number,
        "sheet_name": finding.sheet_name,
        "detection_method": finding.detection_method,
        "redacted_evidence": finding.redacted_evidence,
        "detected_at": finding.detected_at.isoformat(),
    }


def _file_to_backend_payload(file_record) -> dict:
    """Map an agent FileRecordORM row onto the backend's `FileIn` schema."""
    return {
        "path": file_record.path,
        "filename": file_record.filename,
        "extension": file_record.extension,
        "mime_type": file_record.mime_type,
        "size_bytes": file_record.size_bytes,
        "sha256": file_record.sha256,
        "owner": file_record.owner,
        "permissions": file_record.permissions,
        "risk_severity": file_record.risk_severity,
        "risk_score": file_record.risk_score,
        "created_at": file_record.created_at.isoformat() if file_record.created_at else None,
        "modified_at": file_record.modified_at.isoformat() if file_record.modified_at else None,
    }


@pytest.fixture
def agent_scan_report(tmp_path):
    """Run a real agent scan against a temp directory containing synthetic
    PII, then shape the persisted scan/files/findings into the request body
    `POST /api/v1/scans` expects.
    """
    scan_dir = tmp_path / "scan-target"
    scan_dir.mkdir()
    (scan_dir / "employees.csv").write_text(
        f"name,email\nJane Synthetic,{SYNTHETIC_EMAIL}\n"
    )

    engine = make_agent_engine(tmp_path / "agent.db")
    init_agent_db(engine)
    session_factory = make_agent_session_factory(engine)

    # use_presidio=False: the regex+validator detector alone is deterministic
    # and sufficient for a well-formed email address, and avoids pulling in
    # a spaCy model download for this test.
    options = ScanOptions(profile="standard", paths=[scan_dir], use_presidio=False)
    summary = run_scan(options, session_factory)

    assert summary.status.value == "completed"
    assert summary.pii_findings >= 1, "expected the agent to detect the synthetic email"

    with session_scope(session_factory) as session:
        scan_record = get_scan(session, summary.scan_id)
        findings = list_findings(session, scan_id=summary.scan_id)
        files = list(scan_record.files)

        payload = {
            "profile": scan_record.profile,
            "status": scan_record.status,
            "scan_paths": scan_record.scan_paths,
            "started_at": scan_record.started_at.isoformat(),
            "completed_at": scan_record.completed_at.isoformat() if scan_record.completed_at else None,
            "files_discovered": scan_record.files_discovered,
            "files_scanned": scan_record.files_scanned,
            "files_skipped": scan_record.files_skipped,
            "pii_findings": scan_record.pii_findings,
            "secret_findings": scan_record.secret_findings,
            "severity_counts": scan_record.severity_counts,
            "files": [_file_to_backend_payload(f) for f in files],
            "findings": [_finding_to_backend_payload(f) for f in findings],
        }

    return payload


@pytest.fixture(autouse=True)
def _clear_backend_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def backend_client():
    """A real in-process backend app wired to a throwaway SQLite database --
    mirrors backend/tests/conftest.py's `client` fixture.
    """
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_backend_db(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def _override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client, session_factory
    app.dependency_overrides.clear()


@pytest.fixture
def registered_org_admin(backend_client):
    """Seed an organization + admin user directly (there is no public
    self-signup endpoint by design -- see backend/README.md's API design
    notes), then log in for a real JWT.
    """
    client, session_factory = backend_client
    session = session_factory()
    org = Organization(id=uuid.uuid4(), name="Integration Test Org", created_at=datetime.now(timezone.utc))
    admin = User(
        id=uuid.uuid4(), org_id=org.id, email="admin@integration-test.example.com",
        hashed_password=hash_password("integration-test-password"),
        role="admin", is_active=True, created_at=datetime.now(timezone.utc),
    )
    session.add(org)
    session.add(admin)
    session.commit()
    session.close()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "integration-test-password"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_agent_scan_report_flows_into_backend_findings(backend_client, registered_org_admin, agent_scan_report):
    client, _ = backend_client
    admin_headers = registered_org_admin

    # Register an endpoint (as the dashboard admin) to get the long-lived
    # endpoint API token the agent would use to authenticate its own
    # requests -- the real flow described in backend/README.md.
    register = client.post(
        "/api/v1/endpoints/register",
        headers=admin_headers,
        json={"name": "integration-test-endpoint", "hostname": "integration-test-endpoint", "os": "linux"},
    )
    assert register.status_code == 201, register.text
    endpoint_token = register.json()["api_token"]

    # Submit the agent's real scan report using the endpoint's own token.
    submit = client.post(
        "/api/v1/scans",
        json=agent_scan_report,
        headers={"Authorization": f"Bearer {endpoint_token}"},
    )
    assert submit.status_code == 201, submit.text

    # Read findings back as the dashboard user.
    findings_response = client.get("/api/v1/findings", headers=admin_headers)
    assert findings_response.status_code == 200, findings_response.text
    body = findings_response.json()
    findings = body["items"]

    email_findings = [f for f in findings if f["category"] == "email"]
    assert email_findings, f"expected an 'email' finding, got categories: {[f['category'] for f in findings]}"

    email_finding = email_findings[0]
    assert email_finding["is_secret"] is False
    assert SYNTHETIC_EMAIL not in email_finding["redacted_evidence"], (
        "raw email address leaked into a field that is supposed to be redacted"
    )
    assert "@example.com" in email_finding["redacted_evidence"]


@pytest.fixture
def live_backend_server(backend_client):
    """The same real FastAPI app + throwaway DB as `backend_client`, but
    actually bound to a real TCP port via uvicorn in a background thread —
    needed because `BackendClient` uses a synchronous `httpx.Client`, and
    this installed httpx version's `ASGITransport` only implements the
    async request path, not the sync one. A real socket is a more honest
    test of the agent's actual runtime behavior anyway.
    """
    import socket
    import threading
    import time

    import uvicorn

    client, _ = backend_client

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError as exc:
            last_exc = exc
            time.sleep(0.05)
    else:
        raise RuntimeError(f"backend server never started listening on {base_url}") from last_exc

    try:
        yield base_url, client
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_agent_sync_client_uploads_a_real_scan_end_to_end(tmp_path, live_backend_server, registered_org_admin):
    """Unlike the test above (which hand-builds the request body the way
    the backend's ingestion API expects), this drives the agent's actual
    production upload path — `sync.scan_uploader.build_scan_report_payload`
    + `sync.backend_client.BackendClient` — over a real TCP socket against
    the real FastAPI app (uvicorn in a background thread, throwaway DB).
    Also proves the idempotency key (`agent_scan_id`) round-trips:
    submitting the same scan twice must not duplicate it server-side.
    """
    from datasentinel_agent.core.pipeline import ScanOptions, run_scan
    from datasentinel_agent.storage.database import (
        init_db as init_agent_db,
        make_engine as make_agent_engine,
        make_session_factory as make_agent_session_factory,
        session_scope,
    )
    from datasentinel_agent.storage.repository import get_scan
    from datasentinel_agent.sync.backend_client import BackendClient
    from datasentinel_agent.sync.scan_uploader import build_scan_report_payload

    base_url, dashboard_client = live_backend_server
    admin_headers = registered_org_admin

    register = dashboard_client.post(
        "/api/v1/endpoints/register",
        headers=admin_headers,
        json={"name": "sync-client-endpoint", "hostname": "sync-client-endpoint", "os": "linux"},
    )
    assert register.status_code == 201, register.text
    endpoint_token = register.json()["api_token"]

    scan_dir = tmp_path / "scan-target"
    scan_dir.mkdir()
    scan_dir_email = "sync.client.integration@example.com"
    (scan_dir / "employees.csv").write_text(f"name,email\nSync Client,{scan_dir_email}\n")

    agent_engine = make_agent_engine(tmp_path / "agent.db")
    init_agent_db(agent_engine)
    agent_session_factory = make_agent_session_factory(agent_engine)
    options = ScanOptions(profile="standard", paths=[scan_dir], use_presidio=False)
    summary = run_scan(options, agent_session_factory)
    assert summary.pii_findings >= 1

    with session_scope(agent_session_factory) as session:
        scan_record = get_scan(session, summary.scan_id)
        payload = build_scan_report_payload(
            scan_record, list(scan_record.files), list(scan_record.findings), list(scan_record.errors)
        )

    with BackendClient(base_url, endpoint_token) as agent_backend_client:
        agent_backend_client.submit_scan_report(payload)
        # Retried upload (spec section 53) — must not create a duplicate.
        agent_backend_client.submit_scan_report(payload)

    scans = dashboard_client.get("/api/v1/scans", headers=admin_headers).json()
    assert len(scans) == 1, "retried upload created a duplicate scan"

    findings = dashboard_client.get("/api/v1/findings", headers=admin_headers).json()["items"]
    email_findings = [f for f in findings if f["category"] == "email"]
    assert len(email_findings) == 1, "retried upload duplicated findings"
    assert scan_dir_email not in email_findings[0]["redacted_evidence"]
