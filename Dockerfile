# Runtime image: the libtorrent streaming server on the dual-GPU base
# (jellyfin-ffmpeg with NVENC/VAAPI, nginx, GPU runtime). The base provides ffmpeg/ffprobe;
# uv manages its own Python 3.12 venv (the system python on the 22.04 base is 3.10).
FROM stremio-docker-dual:latest

# uv (standalone binary; brings its own Python toolchain)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv/app
# Dependency metadata first (better layer caching), then source.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# Pin Python 3.12: libtorrent 2.0.11 only publishes cp312/cp313 wheels (no 3.14).
RUN uv sync --no-dev --python 3.12

ENV STREMIOSRV_CACHE_ROOT=/root/.stremio-server
ENV PATH="/srv/app/.venv/bin:${PATH}"

# 11470 = streaming-server API (proxied by nginx in production); 6881 = BitTorrent peer port.
EXPOSE 11470 12470 6881
VOLUME ["/root/.stremio-server"]

CMD ["/srv/app/.venv/bin/uvicorn", "stremiosrv.app:build_app", "--factory", \
     "--host", "0.0.0.0", "--port", "11470"]
