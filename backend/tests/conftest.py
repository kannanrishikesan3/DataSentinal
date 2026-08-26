"""Shared test fixtures: a FastAPI TestClient wired to a fresh in-memory
SQLite database per test (dependency-overridden `get_db`), plus helpers to
seed an organization/admin user and get an authenticated client.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from datasentinel_backend.core.config import get_settings
from datasentinel_backend.core.database import get_db, init_db
from datasentinel_backend.main import app
from datasentinel_backend.models.models import Organization, User
from datasentinel_backend.security.passwords import hash_password


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session_factory():
    # StaticPool: every checkout shares the same underlying connection, so
    # the schema created by init_db() is visible to every later session —
    # a plain :memory: engine otherwise hands out a fresh, empty database
    # per connection.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(db_session_factory):
    def _override_get_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def org_and_admin(db_session_factory):
    session = db_session_factory()
    org = Organization(id=uuid.uuid4(), name="Acme Corp", created_at=datetime.now(timezone.utc))
    admin = User(
        id=uuid.uuid4(), org_id=org.id, email="admin@acme-corp.example.com",
        hashed_password=hash_password("correct horse battery staple"),
        role="admin", is_active=True, created_at=datetime.now(timezone.utc),
    )
    session.add(org)
    session.add(admin)
    session.commit()
    session.refresh(org)
    session.refresh(admin)
    session.close()
    return org, admin


@pytest.fixture
def auth_headers(client, org_and_admin):
    _, admin = org_and_admin
    response = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "correct horse battery staple"})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _login_as_role(client, db_session_factory, org, role: str, email: str) -> dict:
    """Seed a user with the given role in `org` and return its auth headers —
    shared by every RBAC test that needs an analyst/viewer alongside the
    `org_and_admin` fixture's admin."""
    session = db_session_factory()
    user = User(
        id=uuid.uuid4(), org_id=org.id, email=email,
        hashed_password=hash_password("correct horse battery staple"),
        role=role, is_active=True, created_at=datetime.now(timezone.utc),
    )
    session.add(user)
    session.commit()
    session.close()

    response = client.post("/api/v1/auth/login", json={"email": email, "password": "correct horse battery staple"})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_auth_headers(client, db_session_factory, org_and_admin):
    org, _ = org_and_admin
    return _login_as_role(client, db_session_factory, org, "viewer", "viewer@acme-corp.example.com")


@pytest.fixture
def analyst_auth_headers(client, db_session_factory, org_and_admin):
    org, _ = org_and_admin
    return _login_as_role(client, db_session_factory, org, "analyst", "analyst@acme-corp.example.com")
