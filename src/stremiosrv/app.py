from fastapi import FastAPI

from stremiosrv import health
from stremiosrv.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Stremio protocol routers (settings/playback/hlsv2/…)
    are registered in later stages from the captured protocol fixtures."""
    settings = settings or Settings()
    app = FastAPI(title="stremio-libtorrent-server")
    app.state.settings = settings
    app.include_router(health.router)
    return app
