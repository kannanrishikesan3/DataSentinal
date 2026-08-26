"""Auth: login succeeds only with correct credentials for an active user,
and every other route requires a valid token."""


def test_login_succeeds_with_correct_credentials(client, org_and_admin):
    _, admin = org_and_admin
    response = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "correct horse battery staple"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_fails_with_wrong_password(client, org_and_admin):
    _, admin = org_and_admin
    response = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "wrong"})
    assert response.status_code == 401


def test_login_fails_for_unknown_email(client):
    response = client.post("/api/v1/auth/login", json={"email": "nobody@nowhere.example.com", "password": "x"})
    assert response.status_code == 401


def test_protected_route_rejects_missing_token(client):
    response = client.get("/api/v1/status")
    assert response.status_code == 401


def test_protected_route_rejects_garbage_token(client):
    response = client.get("/api/v1/status", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_protected_route_accepts_valid_token(client, auth_headers):
    response = client.get("/api/v1/status", headers=auth_headers)
    assert response.status_code == 200


def test_me_returns_current_user(client, auth_headers, org_and_admin):
    _, admin = org_and_admin
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == admin.email
    assert body["role"] == "admin"
