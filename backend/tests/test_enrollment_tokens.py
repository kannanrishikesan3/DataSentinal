"""Enrollment tokens (spec sections 7-13): a reusable, expiring, revocable
credential that lets many endpoints self-register from one token instead
of an admin creating one permanent credential per device by hand."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest


def _create_token(client, auth_headers, **overrides):
    payload = {"name": "Employee Windows Deployment", "expires_in_days": 7, "max_uses": 100}
    payload.update(overrides)
    return client.post("/api/v1/enrollment-tokens", headers=auth_headers, json=payload)


def _enroll(client, raw_token, hostname="EMP-LAPTOP-01", os="windows"):
    return client.post(
        "/api/v1/endpoints/enroll",
        json={"enrollment_token": raw_token, "name": hostname, "hostname": hostname, "os": os},
    )


def test_create_enrollment_token_returns_raw_token_once(client, auth_headers):
    response = _create_token(client, auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["raw_token"].startswith("dset_")
    assert body["token"]["status"] == "active"
    assert body["token"]["current_uses"] == 0
    assert body["token"]["max_uses"] == 100


def test_list_enrollment_tokens_never_includes_the_raw_token(client, auth_headers):
    _create_token(client, auth_headers)
    response = client.get("/api/v1/enrollment-tokens", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert "raw_token" not in body[0]
    assert "hashed_token" not in body[0]
    assert "token" not in body[0]  # flat EnrollmentTokenResponse, not wrapped


def test_creating_a_token_requires_admin(client, db_session_factory, org_and_admin):
    from datasentinel_backend.models.models import User
    from datasentinel_backend.security.passwords import hash_password

    org, _ = org_and_admin
    session = db_session_factory()
    analyst = User(
        id=uuid.uuid4(), org_id=org.id, email="analyst@acme-corp.example.com",
        hashed_password=hash_password("hunter2222"), role="analyst", is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(analyst)
    session.commit()
    session.close()

    login = client.post("/api/v1/auth/login", json={"email": analyst.email, "password": "hunter2222"})
    analyst_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = _create_token(client, analyst_headers)
    assert response.status_code == 403


def test_enroll_with_a_valid_token_creates_an_endpoint_and_issues_a_credential(client, auth_headers):
    created = _create_token(client, auth_headers, allowed_os="windows")
    raw_token = created.json()["raw_token"]

    response = _enroll(client, raw_token, hostname="EMP-LAPTOP-01", os="windows")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["endpoint"]["hostname"] == "EMP-LAPTOP-01"
    assert body["api_token"].startswith("dsat_")  # a normal endpoint token, not the enrollment token

    # The endpoint actually appears in the org's endpoint list.
    listed = client.get("/api/v1/endpoints", headers=auth_headers).json()
    assert any(e["hostname"] == "EMP-LAPTOP-01" for e in listed)

    # And current_uses incremented.
    tokens = client.get("/api/v1/enrollment-tokens", headers=auth_headers).json()
    assert tokens[0]["current_uses"] == 1


def test_enroll_with_wrong_os_is_rejected(client, auth_headers):
    created = _create_token(client, auth_headers, allowed_os="windows")
    raw_token = created.json()["raw_token"]

    response = _enroll(client, raw_token, hostname="EMP-LAPTOP-02", os="linux")
    assert response.status_code == 403

    tokens = client.get("/api/v1/enrollment-tokens", headers=auth_headers).json()
    assert tokens[0]["current_uses"] == 0  # a rejected attempt must not consume a use


def test_enroll_with_an_invalid_token_is_rejected(client):
    response = _enroll(client, "dset_not-a-real-token-at-all", hostname="X")
    assert response.status_code == 401


def test_enroll_with_a_garbage_token_shape_is_rejected(client):
    response = _enroll(client, "totally-not-shaped-like-a-token", hostname="X")
    assert response.status_code == 401


def test_enroll_with_a_revoked_token_is_rejected(client, auth_headers):
    created = _create_token(client, auth_headers)
    token_id = created.json()["token"]["id"]
    raw_token = created.json()["raw_token"]

    revoke = client.post(f"/api/v1/enrollment-tokens/{token_id}/revoke", headers=auth_headers)
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"

    response = _enroll(client, raw_token, hostname="EMP-LAPTOP-03")
    assert response.status_code == 403


def test_enroll_with_an_exhausted_token_is_rejected(client, auth_headers):
    created = _create_token(client, auth_headers, max_uses=1)
    raw_token = created.json()["raw_token"]

    first = _enroll(client, raw_token, hostname="EMP-LAPTOP-04")
    assert first.status_code == 201

    second = _enroll(client, raw_token, hostname="EMP-LAPTOP-05")
    assert second.status_code == 403

    tokens = client.get("/api/v1/enrollment-tokens", headers=auth_headers).json()
    assert tokens[0]["status"] == "exhausted"


def test_enroll_with_an_expired_token_is_rejected(client, auth_headers, db_session_factory):
    from datasentinel_backend.models.models import EnrollmentToken

    created = _create_token(client, auth_headers)
    token_id = created.json()["token"]["id"]
    raw_token = created.json()["raw_token"]

    session = db_session_factory()
    token_row = session.get(EnrollmentToken, uuid.UUID(token_id))
    token_row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    session.commit()
    session.close()

    response = _enroll(client, raw_token, hostname="EMP-LAPTOP-06")
    assert response.status_code == 403


def test_enroll_duplicate_hostname_within_org_conflicts(client, auth_headers):
    created = _create_token(client, auth_headers)
    raw_token = created.json()["raw_token"]

    first = _enroll(client, raw_token, hostname="EMP-LAPTOP-07")
    assert first.status_code == 201
    second = _enroll(client, raw_token, hostname="EMP-LAPTOP-07")
    assert second.status_code == 409


def test_enrollment_tokens_are_scoped_to_organization(client, db_session_factory, auth_headers):
    """A second org's admin must never see the first org's enrollment
    tokens, and a token from org A must never work to enroll into org B."""
    from datasentinel_backend.models.models import Organization, User
    from datasentinel_backend.security.passwords import hash_password

    created = _create_token(client, auth_headers)
    raw_token = created.json()["raw_token"]

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

    tokens = client.get("/api/v1/enrollment-tokens", headers=headers2).json()
    assert tokens == []

    # Enrolling still succeeds (the token is valid), but the resulting
    # endpoint belongs to org A (the token's own org), never org B.
    enroll = _enroll(client, raw_token, hostname="CROSS-ORG-TEST")
    assert enroll.status_code == 201

    org_b_endpoints = client.get("/api/v1/endpoints", headers=headers2).json()
    assert not any(e["hostname"] == "CROSS-ORG-TEST" for e in org_b_endpoints)


def test_revoke_requires_admin(client, db_session_factory, org_and_admin, auth_headers):
    from datasentinel_backend.models.models import User
    from datasentinel_backend.security.passwords import hash_password

    org, _ = org_and_admin
    created = _create_token(client, auth_headers)
    token_id = created.json()["token"]["id"]

    session = db_session_factory()
    viewer = User(
        id=uuid.uuid4(), org_id=org.id, email="viewer@acme-corp.example.com",
        hashed_password=hash_password("hunter2222"), role="viewer", is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(viewer)
    session.commit()
    session.close()

    login = client.post("/api/v1/auth/login", json={"email": viewer.email, "password": "hunter2222"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(f"/api/v1/enrollment-tokens/{token_id}/revoke", headers=viewer_headers)
    assert response.status_code == 403


def test_enrollment_token_with_a_policy_auto_assigns_it_to_the_enrolled_endpoint(client, auth_headers):
    policy = client.post("/api/v1/policies", headers=auth_headers, json={"name": "kiosk-quick-scan", "config": {}})
    policy_id = policy.json()["id"]

    created = _create_token(client, auth_headers, policy_id=policy_id)
    assert created.json()["token"]["policy_id"] == policy_id
    raw_token = created.json()["raw_token"]

    enrolled = _enroll(client, raw_token, hostname="KIOSK-01")
    assert enrolled.status_code == 201
    assert enrolled.json()["endpoint"]["policy_id"] == policy_id

    endpoint_id = enrolled.json()["endpoint"]["id"]
    endpoint_api_token = enrolled.json()["api_token"]
    effective = client.get(
        "/api/v1/policies/effective", headers={"Authorization": f"Bearer {endpoint_api_token}"}
    ).json()
    assert len(effective) == 1
    assert effective[0]["id"] == policy_id

    # And it's reflected on the endpoint's own dashboard record too.
    fetched = client.get(f"/api/v1/endpoints/{endpoint_id}", headers=auth_headers).json()
    assert fetched["policy_id"] == policy_id


def test_enrollment_token_with_an_unknown_policy_id_is_rejected(client, auth_headers):
    response = _create_token(client, auth_headers, policy_id="00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_enrollment_token_actions_are_audit_logged(client, auth_headers):
    created = _create_token(client, auth_headers)
    raw_token = created.json()["raw_token"]
    token_id = created.json()["token"]["id"]

    _enroll(client, raw_token, hostname="EMP-LAPTOP-08")
    client.post(f"/api/v1/enrollment-tokens/{token_id}/revoke", headers=auth_headers)

    logs = client.get("/api/v1/audit-logs", headers=auth_headers).json()
    actions = {entry["action"] for entry in logs}
    assert "enrollment_token.created" in actions
    assert "endpoint.enrolled" in actions
    assert "enrollment_token.revoked" in actions

    # Never the raw token itself, anywhere in the audit trail.
    assert raw_token not in str(logs)
