from stremiosrv.config import Settings


def test_defaults_and_env(monkeypatch):
    monkeypatch.setenv("STREMIOSRV_CACHE_SIZE", "2147483648")
    s = Settings()
    assert s.http_port == 11470
    assert s.bt_listen_port == 6881
    assert s.cache_size == 2147483648
    assert s.cache_root.endswith(".stremio-server")
