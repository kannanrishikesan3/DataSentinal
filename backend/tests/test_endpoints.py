"""Endpoint registration and the resulting API token, which the agent then
uses to authenticate scan submissions."""

import uuid
from datetime import datetime, timezone


def _register(client, auth_headers, hostname="WIN-LAPTOP-023"):
    return client.post(
        "/api/v1/endpoints/register",
        headers=auth_headers,
        json={"name": hostname, "hostname": hostname, "os": "windows", "os_version": "11", "agent_version": "1.0.0"},
    )


def test_register_endpoint_returns_a_usable_api_token(client, auth_headers):
    response = _register(client, auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["endpoint"]["hostname"] == "WIN-LAPTOP-023"
    assert body["api_token"].startswith("dsat_")


def test_register_duplicate_hostname_conflicts(client, auth_headers):
    _register(client, auth_headers)
    response = _register(client, auth_headers)
    assert response.status_code == 409


def test_register_requires_authentication(client):
    response = client.post(
        "/api/v1/endpoints/register",
        json={"name": "x", "hostname": "x", "os": "linux"},
    )
    assert response.status_code == 401


def test_list_endpoints_returns_registered_endpoints(client, auth_headers):
    _register(client, auth_headers)
    response = client.get("/api/v1/endpoints", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_registered_api_token_authenticates_scan_submission(client, auth_headers):
    register_response = _register(client, auth_headers)
    api_token = register_response.json()["api_token"]

    scan_payload = {
        "profile": "standard",
        "status": "completed",
        "scan_paths": ["/home/user"],
        "started_at": "2026-01-01T00:00:00Z",
        "files_discovered": 1,
        "files_scanned": 1,
        "files_skipped": 0,
        "pii_findings": 0,
        "secret_findings": 0,
        "severity_counts": {},
        "files": [],
        "findings": [],
    }
    response = client.post("/api/v1/scans", json=scan_payload, headers={"Authorization": f"Bearer {api_token}"})
    assert response.status_code == 201, response.text


def test_invalid_api_token_is_rejected(client):
    response = client.post(
        "/api/v1/scans",
        json={"profile": "standard", "status": "completed", "started_at": "2026-01-01T00:00:00Z"},
        headers={"Authorization": "Bearer dsat_not-a-real-endpoint-id_secret"},
    )
    assert response.status_code == 401


def _login_as_non_admin(client, db_session_factory, org_and_admin, role="analyst"):
    from datasentinel_backend.models.models import User
    from datasentinel_backend.security.passwords import hash_password

    org, _ = org_and_admin
    session = db_session_factory()
    non_admin = User(
        id=uuid.uuid4(), org_id=org.id, email=f"{role}@acme-corp.example.com",
        hashed_password=hash_password("hunter2222"), role=role, is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(non_admin)
    session.commit()
    session.close()

    login = client.post("/api/v1/auth/login", json={"email": non_admin.email, "password": "hunter2222"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_register_endpoint_requires_admin(client, db_session_factory, org_and_admin):
    """Registration must be admin-only — a non-admin authenticated dashboard
    user must be rejected, even though they hold a valid JWT."""
    analyst_headers = _login_as_non_admin(client, db_session_factory, org_and_admin, role="analyst")
    response = _register(client, analyst_headers)
    assert response.status_code == 403


def test_register_endpoint_succeeds_for_admin(client, auth_headers):
    response = _register(client, auth_headers)
    assert response.status_code == 201


def test_freshly_registered_endpoint_has_no_scan_and_zero_risk(client, auth_headers):
    _register(client, auth_headers)
    response = client.get("/api/v1/endpoints", headers=auth_headers)
    endpoint = response.json()[0]
    assert endpoint["last_scan"] is None
    assert endpoint["risk_score"] == 0


def test_get_endpoint_by_id_returns_the_registered_endpoint(client, auth_headers):
    register_response = _register(client, auth_headers)
    endpoint_id = register_response.json()["endpoint"]["id"]

    response = client.get(f"/api/v1/endpoints/{endpoint_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["hostname"] == "WIN-LAPTOP-023"


def test_get_endpoint_by_id_requires_authentication(client, auth_headers):
    register_response = _register(client, auth_headers)
    endpoint_id = register_response.json()["endpoint"]["id"]

    response = client.get(f"/api/v1/endpoints/{endpoint_id}")
    assert response.status_code == 401


def test_get_endpoint_by_id_returns_404_for_unknown_id(client, auth_headers):
    response = client.get(f"/api/v1/endpoints/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


def test_get_endpoint_by_id_is_scoped_to_organization(client, db_session_factory, auth_headers):
    """An admin in a different organization must never be able to look up
    another org's endpoint by guessing/enumerating its ID (IDOR)."""
    from datasentinel_backend.models.models import Organization, User
    from datasentinel_backend.security.passwords import hash_password

    register_response = _register(client, auth_headers)
    endpoint_id = register_response.json()["endpoint"]["id"]

    session = db_session_factory()
    org2 = Organization(id=uuid.uuid4(), name="Other Org", created_at=datetime.now(timezone.utc))
    admin2 = User(
        id=uuid.uuid4(), org_id=org2.id, email="admin2@other-org.example.com",
        hashed_password=hash_password("hunter22"), role="admin", is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(org2)
    session.add(admin2)
    session.commit()
    session.close()

    login = client.post("/api/v1/auth/login", json={"email": "admin2@other-org.example.com", "password": "hunter22"})
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get(f"/api/v1/endpoints/{endpoint_id}", headers=headers2)
    assert response.status_code == 404


def test_endpoint_reflects_last_scan_and_risk_score_after_scan(client, auth_headers):
    register_response = _register(client, auth_headers)
    api_token = register_response.json()["api_token"]

    scan_payload = {
        "profile": "standard",
        "status": "completed",
        "scan_paths": ["/home/user"],
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:05:00Z",
        "files_discovered": 1,
        "files_scanned": 1,
        "files_skipped": 0,
        "pii_findings": 0,
        "secret_findings": 1,
        "severity_counts": {},
        "files": [{"path": "/tmp/secret.env", "filename": "secret.env", "extension": ".env", "size_bytes": 10}],
        "findings": [
            {
                "finding_id": "f1", "file_path": "/tmp/secret.env", "category": "aws_credentials",
                "is_secret": True, "severity": "high", "confidence": 0.9, "occurrence_count": 1,
                "detection_method": "regex", "redacted_evidence": "[REDACTED]",
                "detected_at": "2026-01-01T00:03:00Z",
            },
        ],
    }
    client.post("/api/v1/scans", json=scan_payload, headers={"Authorization": f"Bearer {api_token}"})

    response = client.get("/api/v1/endpoints", headers=auth_headers)
    endpoint = response.json()[0]
    assert endpoint["last_scan"] is not None
    assert endpoint["last_scan"].startswith("2026-01-01T00:05:00")
    assert endpoint["risk_score"] == 3  # SEVERITY_ORDER["high"]


def test_admin_can_assign_and_clear_an_endpoint_policy(client, auth_headers):
    endpoint_id = _register(client, auth_headers).json()["endpoint"]["id"]
    policy_id = client.post("/api/v1/policies", headers=auth_headers, json={"name": "p", "config": {}}).json()["id"]

    assigned = client.patch(f"/api/v1/endpoints/{endpoint_id}", headers=auth_headers, json={"policy_id": policy_id})
    assert assigned.status_code == 200
    assert assigned.json()["policy_id"] == policy_id

    cleared = client.patch(f"/api/v1/endpoints/{endpoint_id}", headers=auth_headers, json={"policy_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["policy_id"] is None


def test_assigning_an_unknown_policy_to_an_endpoint_is_rejected(client, auth_headers):
    endpoint_id = _register(client, auth_headers).json()["endpoint"]["id"]
    response = client.patch(
        f"/api/v1/endpoints/{endpoint_id}", headers=auth_headers,
        json={"policy_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_non_admin_cannot_assign_an_endpoint_policy(client, auth_headers, viewer_auth_headers):
    endpoint_id = _register(client, auth_headers).json()["endpoint"]["id"]
    response = client.patch(f"/api/v1/endpoints/{endpoint_id}", headers=viewer_auth_headers, json={"policy_id": None})
    assert response.status_code == 403
