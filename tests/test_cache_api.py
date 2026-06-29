from fastapi.testclient import TestClient

from stremiosrv.app import create_app


def test_cache_list_shape(monkeypatch):
    from stremiosrv import cache as cachemod
    monkeypatch.setattr(
        cachemod, "scan_cache",
        lambda root: [{"name": "a.iso", "size": 10, "mtime": 1.0}],
    )
    client = TestClient(create_app())  # engine is None
    body = client.get("/cache.json").json()
    assert body == [
        {"name": "a.iso", "size": 10, "mtime": 1.0, "active": False, "infoHash": None}
    ]


def test_cache_list_marks_active(monkeypatch):
    from stremiosrv import cache as cachemod
    monkeypatch.setattr(
        cachemod, "scan_cache",
        lambda root: [{"name": "a.iso", "size": 10, "mtime": 1.0}],
    )

    class FakeEngine:
        def name_to_hash(self):
            return {"a.iso": "deadbeef"}

    client = TestClient(create_app(engine=FakeEngine()))
    body = client.get("/cache.json").json()
    assert body[0]["active"] is True
    assert body[0]["infoHash"] == "deadbeef"
