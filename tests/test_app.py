from fastapi.testclient import TestClient

from stremiosrv.app import create_app


def test_app_boots_and_health():
    c = TestClient(create_app())
    assert c.get("/health").status_code == 200
