"""Phase 1 smoke test: the FastAPI app boots and /health responds."""

from fastapi.testclient import TestClient

from datasentinel_backend.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "datasentinel-backend"
