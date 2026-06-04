from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Overridable via STREMIOSRV_* env vars."""

    model_config = SettingsConfigDict(env_prefix="STREMIOSRV_")

    http_port: int = 11470
    bt_listen_port: int = 6881
    enable_upnp: bool = True
    cache_root: str = "/root/.stremio-server"
    cache_size: int = 2_147_483_648  # 2 GiB
    bt_max_connections: int = 200
    transcode_profile: str | None = None  # set by HW autodetect (later stage)
