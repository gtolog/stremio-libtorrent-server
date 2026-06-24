# DEVOPS — stremio-libtorrent-server

Deployment and operations for the libtorrent-based Stremio streaming server. This server is a drop-in
replacement for the closed Stremio `server.js`: it implements the streaming-server HTTP API
(handshake, torrent playback with **inbound** peering, hlsv2 transcode, subtitles, opensubHash).

## 1. Automated deployment

### Prerequisites (host)
- Docker Engine + Docker Compose v2.
- An NVIDIA GPU with a driver new enough for the host kernel, plus the NVIDIA Container Toolkit
  (`nvidia-ctk runtime configure`). For GPU driver install — including on a Proxmox/LXC host where the
  driver must be installed at the host level — see `NVIDIA-GPU.md` in the companion image repo.
- (Optional) An Intel iGPU exposed at `/dev/dri/renderD128` for the VAAPI fallback.

### Build & run
The image **always starts**, with or without a GPU — it autodetects the transcode profile at startup
(NVIDIA → `nvenc-linux`, else a VAAPI render node → `vaapi-renderD128`, else CPU/libx264). The GPU is
optional at the orchestration level too, so a missing/broken NVIDIA driver never blocks startup.

**Recommended — durable launcher** (auto-detects GPU, degrades to VAAPI/CPU, safe to re-run):
```sh
docker build -t stremio-libtorrent-server:dev .
DATA=/path/with/certificates.pem ./docker/launch.sh
curl -fsS http://<host>:11470/health
curl http://<host>:11470/hwaccel-profiler   # shows the autodetected profile (null = CPU)
```

**Or with compose** — the base is CPU/VAAPI-safe (starts anywhere); add the GPU overlay only on
hosts with the NVIDIA container runtime:
```sh
docker compose up -d                                   # CPU/VAAPI (always works)
docker compose -f compose.yaml -f compose.gpu.yaml up -d   # + NVENC (NVIDIA hosts)
docker compose ps          # STATUS should show (healthy) once the healthcheck passes
```
> Do **not** put `--gpus all` / `runtime: nvidia` in the always-on path: those hard-fail at container
> creation when the NVIDIA runtime/driver is absent, taking the service down. `launch.sh` (or the
> compose overlay split) keeps startup resilient.

### Configuration (env vars, prefix `STREMIOSRV_`)
| Var | Default | Purpose |
|---|---|---|
| `STREMIOSRV_HTTP_PORT` | `11470` | streaming-server API port |
| `STREMIOSRV_BT_LISTEN_PORT` | `6881` | BitTorrent peer port (TCP+UDP) |
| `STREMIOSRV_CACHE_ROOT` | `/root/.stremio-server` | download/transcode cache |
| `STREMIOSRV_CACHE_SIZE` | `2147483648` | cache size in bytes |
| `STREMIOSRV_BT_MAX_CONNECTIONS` | `200` | libtorrent connection cap |
| `STREMIOSRV_TRANSCODE_PROFILE` | autodetect | force a HW profile |

### Ports / networking
- **11470** — streaming-server API. Put a reverse proxy (TLS) in front for remote clients.
- **6881 TCP+UDP** — BitTorrent peer port. Unlike the stock engine (outbound-only), **this server
  binds an inbound listener**, so forwarding 6881 to the host improves peer connectivity and speeds.

### Health & monitoring
- `GET /health` follows the ITCOM contract: `200` healthy / `503` degraded, body
  `{"status": "...", "components": {...}}`.
- The compose service carries `monitor.*` labels for AHM auto-discovery, plus a Docker `healthcheck`.

### CI/CD
- **Jenkins** — build/push the image and run the test suite (`uv run pytest`, `uv run ruff check`) on
  push; deploy via compose on the target host.
- **Ansible** — a role that installs the GPU driver + container toolkit, renders `compose.yaml`, and
  runs `docker compose up -d`. Target OS: current Debian/Ubuntu LTS.

## 2. Human activities (not automated)
- **GPU driver install** on the host/hypervisor (kernel-coupled; see `NVIDIA-GPU.md`). On Proxmox the
  driver goes on the host and the device is passed into the container.
- **Port-forwarding** 6881 (TCP+UDP) on the edge router for inbound peers.
- **TLS termination / reverse proxy** for remote access (the API serves plain HTTP).
- **Client wiring** — point the Stremio client's streaming-server URL at this server's origin.
