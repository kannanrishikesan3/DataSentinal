"""Standalone exclusion-rule CRUD (`/api/v1/exclusion-rules`) — the
per-finding convenience route (`/findings/{id}/exclusion-rule`) is covered
in test_scans_and_findings.py."""


def test_create_list_and_delete_exclusion_rule(client, auth_headers):
    created = client.post(
        "/api/v1/exclusion-rules", headers=auth_headers,
        json={"category": "email", "reason": "known test fixtures"},
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]

    listed = client.get("/api/v1/exclusion-rules", headers=auth_headers).json()
    assert len(listed) == 1
    assert listed[0]["category"] == "email"

    deleted = client.delete(f"/api/v1/exclusion-rules/{rule_id}", headers=auth_headers)
    assert deleted.status_code == 204

    listed_after = client.get("/api/v1/exclusion-rules", headers=auth_headers).json()
    assert listed_after == []


def test_exclusion_rule_requires_category_or_path_pattern(client, auth_headers):
    response = client.post("/api/v1/exclusion-rules", headers=auth_headers, json={"reason": "no target given"})
    assert response.status_code == 422


def test_viewer_cannot_create_or_delete_exclusion_rule(client, auth_headers, viewer_auth_headers):
    create = client.post(
        "/api/v1/exclusion-rules", headers=viewer_auth_headers, json={"category": "email", "reason": "x"}
    )
    assert create.status_code == 403

    created_by_admin = client.post(
        "/api/v1/exclusion-rules", headers=auth_headers, json={"category": "phone", "reason": "x"}
    )
    rule_id = created_by_admin.json()["id"]
    delete = client.delete(f"/api/v1/exclusion-rules/{rule_id}", headers=viewer_auth_headers)
    assert delete.status_code == 403


def test_analyst_can_create_exclusion_rule(client, analyst_auth_headers):
    response = client.post(
        "/api/v1/exclusion-rules", headers=analyst_auth_headers, json={"path_pattern": "*/scratch/*", "reason": "x"}
    )
    assert response.status_code == 201


def test_exclusion_rule_creation_is_audit_logged(client, auth_headers):
    client.post("/api/v1/exclusion-rules", headers=auth_headers, json={"category": "email", "reason": "x"})
    logs = client.get("/api/v1/audit-logs", headers=auth_headers).json()["items"]
    assert any(entry["action"] == "exclusion_rule.created" for entry in logs)
