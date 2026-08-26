"""Adversarial security tests (spec section 47) beyond ordinary CRUD/auth
coverage: expired tokens, cross-organization IDOR across every by-ID route,
SQL-injection-shaped input, and stored-XSS-shaped input in report rendering.
No offensive tooling — every case here is a normal HTTP request with
adversarial *content*, asserting the app either rejects it cleanly or
neutralizes it before it reaches a response.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from datasentinel_backend.core.config import get_settings
from datasentinel_backend.security.tokens import create_access_token


def test_expired_jwt_is_rejected(client, org_and_admin):
    _, admin = org_and_admin
    settings = get_settings()
    expired_token = create_access_token(
        subject=str(admin.id), secret_key=settings.secret_key, expires_minutes=-5,
    )
    response = client.get("/api/v1/status", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


def test_jwt_signed_with_wrong_secret_is_rejected(client, org_and_admin):
    _, admin = org_and_admin
    forged_token = create_access_token(subject=str(admin.id), secret_key="not-the-real-secret", expires_minutes=30)
    response = client.get("/api/v1/status", headers={"Authorization": f"Bearer {forged_token}"})
    assert response.status_code == 401


def test_jwt_for_a_deleted_or_unknown_user_is_rejected(client):
    settings = get_settings()
    token = create_access_token(subject=str(uuid.uuid4()), secret_key=settings.secret_key, expires_minutes=30)
    response = client.get("/api/v1/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def _other_org_headers(client, db_session_factory):
    from datasentinel_backend.models.models import Organization, User
    from datasentinel_backend.security.passwords import hash_password

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
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _seed_scan_with_finding(client, auth_headers):
    register = client.post(
        "/api/v1/endpoints/register", headers=auth_headers,
        json={"name": "srv-01", "hostname": "srv-01", "os": "linux"},
    )
    api_token = register.json()["api_token"]
    endpoint_id = register.json()["endpoint"]["id"]

    scan_payload = {
        "profile": "standard",
        "status": "completed",
        "scan_paths": ["/home/user"],
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:05:00Z",
        "files_discovered": 1,
        "files_scanned": 1,
        "files_skipped": 0,
        "pii_findings": 1,
        "secret_findings": 0,
        "severity_counts": {"low": 1},
        "files": [{"path": "/home/user/employees.csv", "filename": "employees.csv", "extension": ".csv", "size_bytes": 10}],
        "findings": [
            {
                "finding_id": "f1", "file_path": "/home/user/employees.csv", "category": "email",
                "is_secret": False, "severity": "low", "confidence": 0.9, "occurrence_count": 1,
                "detection_method": "regex", "redacted_evidence": "jo***@example.com",
                "detected_at": "2026-01-01T00:03:00Z",
            },
        ],
    }
    submit = client.post("/api/v1/scans", json=scan_payload, headers={"Authorization": f"Bearer {api_token}"})
    scan_id = submit.json()["id"]
    finding_id = client.get("/api/v1/findings", headers=auth_headers).json()["items"][0]["id"]
    return endpoint_id, scan_id, finding_id


def test_cross_org_idor_is_blocked_on_every_by_id_route(client, db_session_factory, auth_headers):
    """One org must never be able to read another org's resource by
    guessing/enumerating its ID, across every resource type that has one."""
    endpoint_id, scan_id, finding_id = _seed_scan_with_finding(client, auth_headers)
    other_headers = _other_org_headers(client, db_session_factory)

    assert client.get(f"/api/v1/endpoints/{endpoint_id}", headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/scans/{scan_id}", headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/findings/{finding_id}", headers=other_headers).status_code == 404
    assert client.get(f"/api/v1/reports/{scan_id}", headers=other_headers).status_code == 404
    assert client.patch(
        f"/api/v1/findings/{finding_id}", headers=other_headers, json={"status": "suppressed"}
    ).status_code == 404
    assert client.post(f"/api/v1/scans/{scan_id}/cancel", headers=other_headers).status_code == 404


def test_sql_injection_shaped_query_params_are_treated_as_literal_values(client, auth_headers):
    """Every query built through SQLAlchemy's expression API is parameterized
    by construction, but this proves it end to end: injection-shaped input
    in a filter must never error out or return unfiltered/extra data."""
    _seed_scan_with_finding(client, auth_headers)

    payload = "'; DROP TABLE findings; --"
    response = client.get("/api/v1/findings", headers=auth_headers, params={"category": payload})
    assert response.status_code == 200
    assert response.json()["total"] == 0

    # The table must still exist and hold its one real row afterwards.
    still_there = client.get("/api/v1/findings", headers=auth_headers)
    assert still_there.status_code == 200
    assert still_there.json()["total"] == 1


def test_sql_injection_shaped_login_email_is_rejected_not_executed(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "' OR '1'='1", "password": "anything"},
    )
    assert response.status_code in (401, 422)


def test_html_report_escapes_script_content_in_finding_fields(client, auth_headers):
    """A finding's own fields flow into the HTML report; a category or file
    path containing markup must never be emitted unescaped (stored XSS)."""
    register = client.post(
        "/api/v1/endpoints/register", headers=auth_headers,
        json={"name": "srv-02", "hostname": "srv-02", "os": "linux"},
    )
    api_token = register.json()["api_token"]

    malicious_path = "/home/user/<script>alert(document.cookie)</script>.csv"
    scan_payload = {
        "profile": "standard",
        "status": "completed",
        "scan_paths": ["/home/user"],
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:05:00Z",
        "files_discovered": 1,
        "files_scanned": 1,
        "files_skipped": 0,
        "pii_findings": 1,
        "secret_findings": 0,
        "severity_counts": {"low": 1},
        "files": [],
        "findings": [
            {
                "finding_id": "f1", "file_path": malicious_path, "category": "email",
                "is_secret": False, "severity": "low", "confidence": 0.9, "occurrence_count": 1,
                "detection_method": "regex", "redacted_evidence": "<img src=x onerror=alert(1)>",
                "detected_at": "2026-01-01T00:03:00Z",
            },
        ],
    }
    submit = client.post("/api/v1/scans", json=scan_payload, headers={"Authorization": f"Bearer {api_token}"})
    scan_id = submit.json()["id"]

    html_report = client.get(f"/api/v1/reports/{scan_id}?format=html", headers=auth_headers)
    assert html_report.status_code == 200
    assert "<script>alert(document.cookie)</script>" not in html_report.text
    assert "<img src=x onerror=alert(1)>" not in html_report.text
    # The escaped form is present instead of the payload being dropped silently.
    assert "&lt;script&gt;" in html_report.text


def test_enrollment_token_never_appears_in_a_registration_error_response(client, auth_headers):
    """A duplicate-hostname 409 (or any registration error) must not echo
    back anything resembling the freshly issued token."""
    payload = {"name": "dup-host", "hostname": "dup-host", "os": "linux"}
    first = client.post("/api/v1/endpoints/register", headers=auth_headers, json=payload)
    issued_token = first.json()["api_token"]

    second = client.post("/api/v1/endpoints/register", headers=auth_headers, json=payload)
    assert second.status_code == 409
    assert issued_token not in second.text


def test_path_traversal_shaped_scan_path_is_stored_but_never_executed(client, auth_headers):
    """The backend only ever stores/echoes `scan_paths` — it must never be
    interpreted as a real filesystem path server-side."""
    register = client.post(
        "/api/v1/endpoints/register", headers=auth_headers,
        json={"name": "srv-03", "hostname": "srv-03", "os": "linux"},
    )
    api_token = register.json()["api_token"]

    scan_payload = {
        "profile": "standard",
        "status": "completed",
        "scan_paths": ["../../../../etc/passwd", "/home/user/../../etc/shadow"],
        "started_at": "2026-01-01T00:00:00Z",
        "files_discovered": 0,
        "files_scanned": 0,
        "files_skipped": 0,
        "pii_findings": 0,
        "secret_findings": 0,
        "severity_counts": {},
        "files": [],
        "findings": [],
    }
    response = client.post("/api/v1/scans", json=scan_payload, headers={"Authorization": f"Bearer {api_token}"})
    assert response.status_code == 201
    assert response.json()["scan_paths"] == ["../../../../etc/passwd", "/home/user/../../etc/shadow"]
