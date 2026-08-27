"""GET /api/v1/audit-logs search and pagination."""


def test_audit_logs_search_matches_action_substring(client, auth_headers):
    client.post("/api/v1/policies", headers=auth_headers, json={"name": "p1", "config": {}})
    client.post("/api/v1/exclusion-rules", headers=auth_headers, json={"category": "email", "reason": "x"})

    matched = client.get("/api/v1/audit-logs?q=policy", headers=auth_headers).json()
    assert matched["total"] >= 1
    assert all("policy" in entry["action"] for entry in matched["items"])

    no_match = client.get("/api/v1/audit-logs?q=does-not-exist-action", headers=auth_headers).json()
    assert no_match["total"] == 0


def test_audit_logs_pagination_offset_and_limit(client, auth_headers):
    for i in range(3):
        client.post("/api/v1/policies", headers=auth_headers, json={"name": f"policy-{i}", "config": {}})

    page1 = client.get("/api/v1/audit-logs?limit=2&offset=0", headers=auth_headers).json()
    assert page1["total"] >= 3
    assert len(page1["items"]) == 2

    page2 = client.get("/api/v1/audit-logs?limit=2&offset=2", headers=auth_headers).json()
    assert len(page2["items"]) >= 1
