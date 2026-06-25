"""Web-player compatibility: stream Content-Type + external subtitle proxy (v0.2.2)."""
from fastapi.testclient import TestClient

from stremiosrv.api.subs import srt_to_vtt
from stremiosrv.app import create_app
from stremiosrv.stream.fileserver import content_type_for


def test_content_type_known_containers():
    assert content_type_for("Big Buck Bunny.mp4") == "video/mp4"
    assert content_type_for("show.S01E01.mkv") == "video/x-matroska"
    assert content_type_for("clip.webm") == "video/webm"


def test_content_type_unknown_falls_back():
    assert content_type_for("file.weirdext") == "application/octet-stream"


def test_srt_to_vtt_converts_timestamps_and_header():
    out = srt_to_vtt("1\n00:00:01,000 --> 00:00:02,500\nHello\n")
    assert out.startswith("WEBVTT")
    assert "00:00:01.000 --> 00:00:02.500" in out


def test_srt_to_vtt_passes_through_existing_vtt():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi\n"
    assert srt_to_vtt(vtt) == vtt


def test_subtitles_proxy_rejects_non_http_scheme():
    # SSRF guard: only http(s) sources allowed (no file://, etc.).
    client = TestClient(create_app(engine=None))
    r = client.get("/subtitles.vtt", params={"from": "file:///etc/passwd"})
    assert r.status_code == 400
