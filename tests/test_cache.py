from stremiosrv.cache import scan_cache, select_evictions


def test_select_none_when_under_budget():
    items = [{"name": "a", "size": 100, "mtime": 1}, {"name": "b", "size": 100, "mtime": 2}]
    assert select_evictions(items, budget=1000) == []


def test_select_oldest_first_until_target():
    items = [
        {"name": "old", "size": 600, "mtime": 1},
        {"name": "mid", "size": 600, "mtime": 2},
        {"name": "new", "size": 600, "mtime": 3},
    ]
    # total 1800, budget 1000 (target 900): drop old+mid -> 600 <= 900
    victims = [v["name"] for v in select_evictions(items, budget=1000)]
    assert victims == ["old", "mid"]


def test_select_skips_in_use():
    items = [{"name": "old", "size": 1000, "mtime": 1}, {"name": "new", "size": 1000, "mtime": 2}]
    victims = [v["name"] for v in select_evictions(items, budget=500, in_use=frozenset({"old"}))]
    assert victims == ["new"]  # oldest is in use -> protected


def test_scan_skips_protected(tmp_path):
    (tmp_path / "certificates.pem").write_bytes(b"x")
    (tmp_path / "movie.mkv").write_bytes(b"y" * 100)
    (tmp_path / "transcode").mkdir()
    names = {i["name"] for i in scan_cache(str(tmp_path))}
    assert "movie.mkv" in names
    assert "certificates.pem" not in names
    assert "transcode" not in names


def test_scan_dir_size(tmp_path):
    d = tmp_path / "show"
    d.mkdir()
    (d / "ep.mkv").write_bytes(b"z" * 500)
    items = {i["name"]: i for i in scan_cache(str(tmp_path))}
    assert items["show"]["size"] == 500
