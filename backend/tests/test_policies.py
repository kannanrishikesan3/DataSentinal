"""Policy CRUD and org scoping."""

import pytest


@pytest.fixture
def endpoint_token(client, auth_headers):
    response = client.post(
        "/api/v1/endpoints/register", headers=auth_headers,
        json={"name": "srv-01", "hostname": "srv-01", "os": "linux"},
    )
    return response.json()["api_token"]


def test_create_and_list_policy(client, auth_headers):
    create = client.post(
        "/api/v1/policies", headers=auth_headers,
        json={"name": "default-deep-scan", "config": {"aggregation_category_threshold": 2}},
    )
    assert create.status_code == 201

    listed = client.get("/api/v1/policies", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["name"] == "default-deep-scan"


def test_duplicate_policy_name_conflicts(client, auth_headers):
    payload = {"name": "dup", "config": {}}
    client.post("/api/v1/policies", headers=auth_headers, json=payload)
    response = client.post("/api/v1/policies", headers=auth_headers, json=payload)
    assert response.status_code == 409


def test_update_policy(client, auth_headers):
    create = client.post("/api/v1/policies", headers=auth_headers, json={"name": "p1", "config": {"a": 1}})
    policy_id = create.json()["id"]

    update = client.patch(
        f"/api/v1/policies/{policy_id}", headers=auth_headers, json={"name": "p1", "config": {"a": 2}}
    )
    assert update.status_code == 200
    assert update.json()["config"] == {"a": 2}


def test_policies_require_authentication(client):
    response = client.get("/api/v1/policies")
    assert response.status_code == 401


def test_endpoint_can_fetch_effective_policies_with_its_own_token(client, auth_headers, endpoint_token):
    client.post(
        "/api/v1/policies", headers=auth_headers,
        json={"name": "default-deep-scan", "config": {"aggregation_category_threshold": 2}},
    )

    response = client.get("/api/v1/policies/effective", headers={"Authorization": f"Bearer {endpoint_token}"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "default-deep-scan"


def test_effective_policies_reject_a_dashboard_user_token(client, auth_headers):
    response = client.get("/api/v1/policies/effective", headers=auth_headers)
    assert response.status_code == 401


def test_effective_policies_require_authentication(client):
    response = client.get("/api/v1/policies/effective")
    assert response.status_code == 401


def test_analyst_cannot_create_policy(client, analyst_auth_headers):
    response = client.post("/api/v1/policies", headers=analyst_auth_headers, json={"name": "p", "config": {}})
    assert response.status_code == 403


def test_viewer_cannot_create_policy(client, viewer_auth_headers):
    response = client.post("/api/v1/policies", headers=viewer_auth_headers, json={"name": "p", "config": {}})
    assert response.status_code == 403


def test_analyst_cannot_update_or_delete_policy(client, auth_headers, analyst_auth_headers):
    created = client.post("/api/v1/policies", headers=auth_headers, json={"name": "p2", "config": {}})
    policy_id = created.json()["id"]

    update = client.patch(
        f"/api/v1/policies/{policy_id}", headers=analyst_auth_headers, json={"name": "p2", "config": {"a": 1}}
    )
    assert update.status_code == 403

    delete = client.delete(f"/api/v1/policies/{policy_id}", headers=analyst_auth_headers)
    assert delete.status_code == 403


def test_admin_can_delete_policy(client, auth_headers):
    created = client.post("/api/v1/policies", headers=auth_headers, json={"name": "p3", "config": {}})
    policy_id = created.json()["id"]

    delete = client.delete(f"/api/v1/policies/{policy_id}", headers=auth_headers)
    assert delete.status_code == 204

    listed = client.get("/api/v1/policies", headers=auth_headers).json()
    assert not any(p["id"] == policy_id for p in listed)


def test_endpoint_with_an_assigned_policy_gets_only_that_one(client, auth_headers, endpoint_token, db_session_factory):
    from datasentinel_backend.security.tokens import parse_endpoint_api_token
    from datasentinel_backend.models.models import Endpoint
    import uuid as uuid_module

    client.post("/api/v1/policies", headers=auth_headers, json={"name": "org-wide", "config": {}})
    assigned = client.post("/api/v1/policies", headers=auth_headers, json={"name": "assigned-one", "config": {"x": 1}})
    policy_id = assigned.json()["id"]

    endpoint_id = parse_endpoint_api_token(endpoint_token)
    session = db_session_factory()
    endpoint = session.get(Endpoint, uuid_module.UUID(endpoint_id))
    endpoint.policy_id = uuid_module.UUID(policy_id)
    session.commit()
    session.close()

    response = client.get("/api/v1/policies/effective", headers={"Authorization": f"Bearer {endpoint_token}"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "assigned-one"
