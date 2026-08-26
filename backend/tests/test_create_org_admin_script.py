"""The `scripts/create_org_admin.py` bootstrap script is the only way to get
a first admin into a fresh deployment (there is no public signup endpoint —
see the script's own docstring for why). Runs it against a real temp-file
SQLite database (not the in-memory :memory: pattern `conftest.py` uses for
API tests, since this script opens its own engine/session directly) and
verifies the resulting user can actually log in.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def bootstrap_db(tmp_path, monkeypatch):
    db_path = tmp_path / "bootstrap.db"
    monkeypatch.setenv("DATASENTINEL_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATASENTINEL_SECRET_KEY", "test-secret-key-for-bootstrap-script")

    from datasentinel_backend.core.config import get_settings
    from datasentinel_backend.core.database import reset_database_state

    get_settings.cache_clear()
    reset_database_state()
    yield
    get_settings.cache_clear()
    reset_database_state()


def _invoke(module, args: list[str]) -> int:
    old_argv = sys.argv
    sys.argv = ["create_org_admin.py", *args]
    try:
        return module.main()
    finally:
        sys.argv = old_argv


def test_bootstrap_creates_org_and_admin_that_can_log_in(bootstrap_db):
    import create_org_admin
    importlib.reload(create_org_admin)

    exit_code = _invoke(
        create_org_admin,
        ["--org", "Acme Corp", "--email", "admin@acme.example.com", "--password", "correct horse battery staple"],
    )
    assert exit_code == 0

    from fastapi.testclient import TestClient
    from datasentinel_backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login", json={"email": "admin@acme.example.com", "password": "correct horse battery staple"}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_bootstrap_is_idempotent_and_resets_password(bootstrap_db):
    import create_org_admin
    importlib.reload(create_org_admin)

    _invoke(create_org_admin, ["--org", "Acme Corp", "--email", "admin@acme.example.com", "--password", "first-password123"])
    exit_code = _invoke(
        create_org_admin, ["--org", "Acme Corp", "--email", "admin@acme.example.com", "--password", "second-password456"]
    )
    assert exit_code == 0

    from fastapi.testclient import TestClient
    from datasentinel_backend.main import app

    client = TestClient(app)

    old_password = client.post(
        "/api/v1/auth/login", json={"email": "admin@acme.example.com", "password": "first-password123"}
    )
    assert old_password.status_code == 401

    new_password = client.post(
        "/api/v1/auth/login", json={"email": "admin@acme.example.com", "password": "second-password456"}
    )
    assert new_password.status_code == 200

    from datasentinel_backend.core.database import get_session_factory
    from datasentinel_backend.models.models import Organization

    session = get_session_factory()()
    try:
        orgs = session.query(Organization).filter(Organization.name == "Acme Corp").all()
        assert len(orgs) == 1  # re-running never creates a duplicate organization
    finally:
        session.close()


def test_bootstrap_rejects_a_short_password(bootstrap_db):
    import create_org_admin
    importlib.reload(create_org_admin)

    exit_code = _invoke(create_org_admin, ["--org", "Acme Corp", "--email", "admin@acme.example.com", "--password", "short"])
    assert exit_code == 1


def test_bootstrap_refuses_to_move_an_email_to_a_different_organization(bootstrap_db):
    import create_org_admin
    importlib.reload(create_org_admin)

    _invoke(create_org_admin, ["--org", "Org One", "--email", "admin@acme.example.com", "--password", "correct horse battery staple"])
    exit_code = _invoke(
        create_org_admin, ["--org", "Org Two", "--email", "admin@acme.example.com", "--password", "correct horse battery staple"]
    )
    assert exit_code == 1
