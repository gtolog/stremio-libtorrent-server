from fastapi.testclient import TestClient

from stremiosrv.app import create_app


def test_health_ok():
    c = TestClient(create_app())
    r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("healthy", "degraded", "unhealthy")
    assert "components" in body
