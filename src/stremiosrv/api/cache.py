from fastapi import APIRouter, Request
from pydantic import BaseModel

from stremiosrv import cache as cachemod

router = APIRouter()


class RemoveBody(BaseModel):
    name: str


def _name_to_hash(engine) -> dict:
    return engine.name_to_hash() if engine is not None else {}


@router.get("/cache.json")
def cache_list(request: Request) -> list[dict]:
    """On-disk cache entries (the LRU store) — distinct from /active.json (loaded torrents).
    Content-neutral: names only, the owner's own box."""
    s = request.app.state.settings
    name_hash = _name_to_hash(request.app.state.engine)
    out = []
    for item in cachemod.scan_cache(s.cache_root):
        ih = name_hash.get(item["name"])
        out.append({
            "name": item["name"],
            "size": item["size"],
            "mtime": item["mtime"],
            "active": ih is not None,
            "infoHash": ih,
        })
    return out
