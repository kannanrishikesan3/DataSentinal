"""End-to-end: register an endpoint, submit a scan with findings, then
verify it's retrievable, filterable, and its status is patchable."""

import pytest


@pytest.fixture
def endpoint_token(client, auth_headers):
    response = client.post(
        "/api/v1/endpoints/register", headers=auth_headers,
        json={"name": "srv-01", "hostname": "srv-01", "os": "linux"},
    )
    return response.json()["api_token"]


def _sample_scan_payload():
    return {
        "profile": "standard",
        "status": "completed",
        "scan_paths": ["/home/user"],
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:05:00Z",
        "files_discovered": 2,
        "files_scanned": 2,
        "files_skipped": 0,
        "pii_findings": 1,
        "secret_findings": 1,
        "severity_counts": {"critical": 1, "high": 0, "medium": 0, "low": 1, "informational": 0},
        "files": [
            {"path": "/home/user/employees.csv", "filename": "employees.csv", "extension": ".csv", "size_bytes": 100},
        ],
        "findings": [
            {
                "finding_id": "f1", "file_path": "/home/user/employees.csv", "category": "email",
                "is_secret": False, "severity": "low", "confidence": 0.9, "occurrence_count": 2,
                "detection_method": "regex", "redacted_evidence": "jo***@example.com",
                "detected_at": "2026-01-01T00:03:00Z",
            },
            {
                "finding_id": "f2", "file_path": "/home/user/config.log", "category": "aws_credentials",
                "is_secret": True, "severity": "critical", "confidence": 0.95, "occurrence_count": 1,
                "detection_method": "regex", "redacted_evidence": "[REDACTED_AWS_CREDENTIALS:20 chars]",
                "detected_at": "2026-01-01T00:04:00Z",
            },
        ],
    }


def test_submit_and_retrieve_scan(client, endpoint_token, auth_headers):
    submit = client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    assert submit.status_code == 201
    scan_id = submit.json()["id"]

    get_response = client.get(f"/api/v1/scans/{scan_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["pii_findings"] == 1


def test_resubmitting_the_same_agent_scan_id_does_not_duplicate(client, endpoint_token, auth_headers):
    """Spec section 53 — a retried upload (e.g. the agent's offline queue
    retrying after a network failure that may have actually succeeded
    server-side) must never create a second scan or duplicate findings."""
    payload = _sample_scan_payload()
    payload["agent_scan_id"] = "agent-local-scan-id-123"

    first = client.post("/api/v1/scans", json=payload, headers={"Authorization": f"Bearer {endpoint_token}"})
    assert first.status_code == 201
    second = client.post("/api/v1/scans", json=payload, headers={"Authorization": f"Bearer {endpoint_token}"})
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    all_scans = client.get("/api/v1/scans", headers=auth_headers).json()["items"]
    assert len(all_scans) == 1

    all_findings = client.get("/api/v1/findings", headers=auth_headers).json()
    assert all_findings["total"] == 2  # not 4 — the retry didn't re-ingest findings


def test_different_agent_scan_ids_create_separate_scans(client, endpoint_token, auth_headers):
    payload_a = _sample_scan_payload()
    payload_a["agent_scan_id"] = "scan-a"
    payload_b = _sample_scan_payload()
    payload_b["agent_scan_id"] = "scan-b"

    client.post("/api/v1/scans", json=payload_a, headers={"Authorization": f"Bearer {endpoint_token}"})
    client.post("/api/v1/scans", json=payload_b, headers={"Authorization": f"Bearer {endpoint_token}"})

    all_scans = client.get("/api/v1/scans", headers=auth_headers).json()["items"]
    assert len(all_scans) == 2


def test_omitting_agent_scan_id_still_works_unchanged(client, endpoint_token, auth_headers):
    """Backwards compatibility: a submission with no agent_scan_id at all
    (older agent, or the field genuinely omitted) still ingests normally,
    just without dedup protection."""
    payload = _sample_scan_payload()
    response = client.post("/api/v1/scans", json=payload, headers={"Authorization": f"Bearer {endpoint_token}"})
    assert response.status_code == 201


def test_list_scans_for_org(client, endpoint_token, auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    response = client.get("/api/v1/scans", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_cancel_scan(client, endpoint_token, auth_headers):
    submit = client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    scan_id = submit.json()["id"]
    response = client.post(f"/api/v1/scans/{scan_id}/cancel", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_findings_are_ingested_and_filterable(client, endpoint_token, auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})

    all_findings = client.get("/api/v1/findings", headers=auth_headers).json()
    assert all_findings["total"] == 2

    secrets_only = client.get("/api/v1/findings?is_secret=true", headers=auth_headers).json()
    assert secrets_only["total"] == 1
    assert secrets_only["items"][0]["category"] == "aws_credentials"

    critical_only = client.get("/api/v1/findings?severity=critical", headers=auth_headers).json()
    assert critical_only["total"] == 1


def test_findings_are_filterable_by_file_type_and_date_range(client, endpoint_token, auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})

    csv_only = client.get("/api/v1/findings?file_type=csv", headers=auth_headers).json()
    assert csv_only["total"] == 1
    assert csv_only["items"][0]["category"] == "email"

    in_range = client.get(
        "/api/v1/findings?detected_after=2026-01-01T00:00:00Z&detected_before=2026-01-01T23:59:59Z",
        headers=auth_headers,
    ).json()
    assert in_range["total"] == 2

    out_of_range = client.get("/api/v1/findings?detected_after=2026-02-01T00:00:00Z", headers=auth_headers).json()
    assert out_of_range["total"] == 0


def test_finding_never_exposes_raw_secret_value(client, endpoint_token, auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    findings = client.get("/api/v1/findings", headers=auth_headers).json()["items"]
    for finding in findings:
        assert "AKIA" not in finding["redacted_evidence"]


def test_update_finding_status_to_false_positive(client, endpoint_token, auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    finding_id = client.get("/api/v1/findings", headers=auth_headers).json()["items"][0]["id"]

    response = client.patch(f"/api/v1/findings/{finding_id}", json={"status": "false_positive"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "false_positive"


def test_finding_status_change_is_audit_logged(client, endpoint_token, auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    finding_id = client.get("/api/v1/findings", headers=auth_headers).json()["items"][0]["id"]
    client.patch(f"/api/v1/findings/{finding_id}", json={"status": "suppressed"}, headers=auth_headers)

    logs = client.get("/api/v1/audit-logs", headers=auth_headers).json()["items"]
    assert any(entry["action"] == "finding.status_changed" for entry in logs)


def test_viewer_cannot_change_finding_status(client, endpoint_token, auth_headers, viewer_auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    finding_id = client.get("/api/v1/findings", headers=auth_headers).json()["items"][0]["id"]

    response = client.patch(
        f"/api/v1/findings/{finding_id}", json={"status": "false_positive"}, headers=viewer_auth_headers
    )
    assert response.status_code == 403


def test_analyst_can_change_finding_status(client, endpoint_token, auth_headers, analyst_auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    finding_id = client.get("/api/v1/findings", headers=auth_headers).json()["items"][0]["id"]

    response = client.patch(
        f"/api/v1/findings/{finding_id}", json={"status": "reopened"}, headers=analyst_auth_headers
    )
    assert response.status_code == 200


def test_viewer_cannot_create_exclusion_rule_from_finding(client, endpoint_token, auth_headers, viewer_auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    finding_id = client.get("/api/v1/findings", headers=auth_headers).json()["items"][0]["id"]

    response = client.post(
        f"/api/v1/findings/{finding_id}/exclusion-rule", json={"reason": "noisy"}, headers=viewer_auth_headers
    )
    assert response.status_code == 403


def test_report_formats(client, endpoint_token, auth_headers):
    submit = client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    scan_id = submit.json()["id"]

    for fmt in ("json", "csv", "html", "text"):
        response = client.get(f"/api/v1/reports/{scan_id}?format={fmt}", headers=auth_headers)
        assert response.status_code == 200, (fmt, response.text)
        assert "AKIA" not in response.text


def test_report_includes_scan_errors(client, endpoint_token, auth_headers):
    payload = _sample_scan_payload()
    payload["errors"] = [
        {
            "path": "/home/user/locked.docx",
            "error_type": "permission_denied",
            "message": "Could not open file: permission denied",
            "occurred_at": "2026-01-01T00:02:00Z",
        }
    ]
    submit = client.post("/api/v1/scans", json=payload, headers={"Authorization": f"Bearer {endpoint_token}"})
    scan_id = submit.json()["id"]

    json_response = client.get(f"/api/v1/reports/{scan_id}?format=json", headers=auth_headers)
    assert json_response.status_code == 200
    json_errors = json_response.json()["errors"]
    assert len(json_errors) == 1
    assert json_errors[0]["path"] == "/home/user/locked.docx"
    assert json_errors[0]["error_type"] == "permission_denied"
    assert json_errors[0]["message"] == "Could not open file: permission denied"

    csv_response = client.get(f"/api/v1/reports/{scan_id}?format=csv", headers=auth_headers)
    assert csv_response.status_code == 200
    assert "/home/user/locked.docx" in csv_response.text
    assert "permission_denied" in csv_response.text
    assert "Could not open file: permission denied" in csv_response.text


def test_dashboard_overview_reflects_ingested_data(client, endpoint_token, auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})
    overview = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()

    assert overview["endpoints_total"] == 1
    assert overview["pii_findings_total"] == 1
    assert overview["secret_findings_total"] == 1
    assert overview["critical_findings"] == 1


def test_findings_are_scoped_to_organization(client, db_session_factory):
    """A second org's admin must never see the first org's findings."""
    import uuid
    from datetime import datetime, timezone

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
    headers2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    findings = client.get("/api/v1/findings", headers=headers2).json()
    assert findings["total"] == 0


def test_findings_search_by_file_path(client, endpoint_token, auth_headers):
    client.post("/api/v1/scans", json=_sample_scan_payload(), headers={"Authorization": f"Bearer {endpoint_token}"})

    matched = client.get("/api/v1/findings?q=employees", headers=auth_headers).json()
    assert matched["total"] == 1
    assert matched["items"][0]["category"] == "email"

    no_match = client.get("/api/v1/findings?q=nonexistent-file", headers=auth_headers).json()
    assert no_match["total"] == 0


def test_scans_pagination_offset_and_limit(client, endpoint_token, auth_headers):
    for i in range(3):
        payload = _sample_scan_payload()
        payload["agent_scan_id"] = f"scan-{i}"
        client.post("/api/v1/scans", json=payload, headers={"Authorization": f"Bearer {endpoint_token}"})

    page1 = client.get("/api/v1/scans?limit=2&offset=0", headers=auth_headers).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2

    page2 = client.get("/api/v1/scans?limit=2&offset=2", headers=auth_headers).json()
    assert len(page2["items"]) == 1
