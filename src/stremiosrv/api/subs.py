"""Subtitle + opensub-hash API: matching key for subtitle addons, embedded-track listing/extraction."""
from __future__ import annotations

import os
import re
import subprocess
import time

from fastapi import APIRouter, HTTPException, Request, Response

from stremiosrv.stream.fileserver import file_disk_path
from stremiosrv.subs.opensub import opensubtitles_hash
from stremiosrv.transcode.probe import probe_media

router = APIRouter()

# Stremio passes videoUrl as our own stream URL: .../<40-hex-infohash>/<fileIdx>[?...]
_STREAM_RE = re.compile(r"/([0-9a-fA-F]{40})/(\d+)")


def parse_stream_url(url: str) -> tuple[str, int] | None:
    m = _STREAM_RE.search(url)
    return (m.group(1).lower(), int(m.group(2))) if m else None


def _ensure_edges(handle, idx: int, edge: int = 65536, timeout: float = 15.0) -> bool:
    """Make sure the first and last `edge` bytes of file `idx` are downloaded (the only bytes the
    OpenSubtitles hash reads), by boosting the covering pieces and waiting briefly."""
    size = handle.file_size(idx)
    if not size:
        return False
    plen = handle.piece_length()
    base = handle.file_offset(idx)
    spans = [(base, base + min(edge, size) - 1), (base + max(0, size - edge), base + size - 1)]
    pieces = sorted({p for lo, hi in spans for p in range(lo // plen, hi // plen + 1)})
    for p in pieces:
        handle.boost_piece(p, 0)
    end = time.time() + timeout
    while time.time() < end and not all(handle.have_piece(p) for p in pieces):
        time.sleep(0.2)
    return all(handle.have_piece(p) for p in pieces)


@router.get("/opensubHash")
def opensub_hash(request: Request, videoUrl: str | None = None, mediaURL: str | None = None) -> dict:
    src = videoUrl or mediaURL
    if not src:
        raise HTTPException(status_code=422, detail="videoUrl or mediaURL required")
    parsed = parse_stream_url(src)
    eng = getattr(request.app.state, "engine", None)
    if parsed is not None and eng is not None:
        info_hash, idx = parsed
        h = eng.get(info_hash) or eng.add(info_hash)
        end = time.time() + 20
        while not h.has_metadata() and time.time() < end:
            time.sleep(0.2)
        if h.has_metadata() and _ensure_edges(h, idx):
            return {"result": opensubtitles_hash(file_disk_path(eng.save_path(), h, idx))}
        return {"result": None}  # couldn't resolve in time -> client falls back to filename match
    if os.path.exists(src):
        return {"result": opensubtitles_hash(src)}
    return {"result": None}


@router.get("/{info_hash}/{idx:int}/subtitles.json")
def subtitles_list(info_hash: str, idx: int, mediaURL: str) -> dict:
    pr = probe_media(mediaURL)
    subs = [
        {"id": s.get("id"), "track": s.get("index"), "codec": s.get("codec"), "lang": s.get("lang")}
        for s in pr["streams"]
        if s.get("track") == "subtitle"
    ]
    return {"subtitles": subs}


@router.get("/{info_hash}/{idx:int}/subtitles.vtt")
def subtitles_vtt(info_hash: str, idx: int, mediaURL: str, track: int = 0) -> Response:
    argv = ["ffmpeg", "-hide_banner", "-y", "-i", mediaURL,
            "-map", f"0:s:{track}", "-f", "webvtt", "pipe:1"]
    proc = subprocess.run(argv, capture_output=True, timeout=60)
    if proc.returncode != 0:
        raise HTTPException(status_code=404, detail="subtitle track not found")
    return Response(content=proc.stdout, media_type="text/vtt")
