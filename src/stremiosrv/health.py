from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/health")
def health(response: Response) -> dict:
    """ITCOM health contract: 200 healthy / 503 degraded|unhealthy.

    Components reflect real dependencies; libtorrent/ffmpeg are added in later stages.
    """
    components = {"http": "ok"}
    status = "healthy" if all(v == "ok" for v in components.values()) else "degraded"
    response.status_code = 200 if status == "healthy" else 503
    return {"status": status, "components": components}
