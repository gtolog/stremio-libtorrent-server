# 🎬 stremio-libtorrent-server

### Your own Stremio streaming server — open, fast, and *yours*. One command to run it. 🚀

Self-host the **complete Stremio experience** — the **web player** *and* a powerful, open
**BitTorrent streaming engine** — in a single container on your own hardware. Point any Stremio
client (browser, Android TV, Tizen, webOS, desktop) at it and press play.

No subscription. No tracking. No black box. **100% free and open — our gift to the community.** 💛

[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-androshack%2Fstremio--libtorrent--server-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/androshack/stremio-libtorrent-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-3DA639.svg)](LICENSE)

---

## ✨ Why you'll love it

- **🚀 Install in one command.** `docker run …` — that's the whole setup. No building, no config files.
- **📺 Just works on TVs.** Automatic **trusted HTTPS** (a real Let's Encrypt cert) that smart TVs actually accept — zero certificate headaches.
- **⚡ Faster, more reliable.** Unlike the closed stock server, this one **accepts inbound peers** and fetches **playhead-first**, so streams start quicker and hold up on thin swarms.
- **🎛️ Truly yours to control.** Real dials for cache, buffering, peers, and transcode — tune deeply, or never touch a thing.
- **🖥️ Hardware transcode, optional.** Intel **VAAPI** / NVIDIA **NVENC** when available, graceful CPU fallback — and a missing GPU never stops it from starting.
- **🧩 Your addons, your choice.** It's **neutral infrastructure**: it streams whatever a Stremio addon hands it. It bundles no content and is not a source.
- **🔓 Open source.** Read it, change it, trust it.

---

## 🚀 Quick Start — anyone can do this

**1.** Install [Docker](https://docs.docker.com/get-docker/).
**2.** Run one command — swap `YOUR_SERVER_IP` for your machine's LAN IP (e.g. `192.168.1.50`):

```sh
docker run -d --name stremio --restart unless-stopped \
  -e IPADDRESS=YOUR_SERVER_IP \
  -p 8080:8080 -p 12470:12470 -p 6881:6881/tcp -p 6881:6881/udp \
  -v stremio-data:/root/.stremio-server \
  androshack/stremio-libtorrent-server
```

**3.** Open it:
- 🌐 **In a browser (same network):** `http://YOUR_SERVER_IP:8080`
- 🔒 **Trusted HTTPS (and TVs):** run `docker logs stremio` and use the printed URL — it looks like
  `https://192-168-1-50.519b6502d940.stremio.rocks:12470`.

Sign into Stremio, add your addons, press play. 🍿
*(Prefer a file? Grab [`compose.hub.yaml`](compose.hub.yaml) → `IPADDRESS=YOUR_SERVER_IP docker compose -f compose.hub.yaml up -d`.)*

---

## 📺 On your TV

Smart TVs insist on a **trusted** HTTPS connection — a self-signed cert won't do. Set `IPADDRESS`
and this server fetches a real Let's Encrypt certificate for you automatically (via Stremio's
`*.stremio.rocks` magic DNS, which maps that long URL back to your server's IP — even on your LAN).
In the TV's Stremio app, set the **Streaming Server URL** to the `…stremio.rocks:12470` address shown
by `docker logs stremio`.

---

## 🌍 Want the *full* swarm? Forward one port.

A lot of BitTorrent's speed comes from peers reaching **you** — and home routers block that by
default. For maximum peers and throughput, **forward port `6881` (TCP *and* UDP)** on your router to
your server. It works fine without forwarding — you'll just reach fewer peers on sparse torrents.
(Unlike the stock server, this one actually *listens* for inbound peers, so the forward genuinely pays off.)

---

## 🔧 Advanced — tune it your way

Everything is a plain `-e NAME=value` environment variable:

| Setting | Default | What it does |
|---|---|---|
| `IPADDRESS` | *(unset)* | Your server IP → auto **trusted TV cert** via `*.stremio.rocks`. Unset → self-signed. |
| `SERVER_URL` | auto | URL the web player targets. Set for a custom domain. |
| `STREMIOSRV_CACHE_SIZE` | `19327352832` (18 GiB) | Download-cache budget in bytes (LRU-evicted). Keep it **above your largest file**. |
| `STREMIOSRV_READAHEAD_BYTES` | `134217728` (128 MiB) | Playhead buffer — bigger absorbs more swarm jitter (fewer rebuffers). |
| `STREMIOSRV_BT_LISTEN_PORT` | `6881` | BitTorrent peer port (the one to forward). |
| `STREMIOSRV_BT_MAX_CONNECTIONS` | `400` | Max peer connections. |
| `DOMAIN` | `localhost` | CN for the self-signed cert (when not using `IPADDRESS`). |
| `CERT_FILE` | `certificates.pem` | Bring-your-own cert (full-chain + key) filename in the data volume. |

**GPU transcode** (only for clients that can't direct-play):
- Intel VAAPI → add `--device /dev/dri:/dev/dri`
- NVIDIA NVENC → use the **[`docker/launch.sh`](docker/launch.sh)** launcher, which probes the GPU and
  degrades gracefully (a broken or absent driver never blocks startup).

**Your own domain instead of stremio.rocks:** put a full-chain+key PEM as `certificates.pem` in the
data volume, set `-e SERVER_URL=https://yourdomain:12470`, and leave `IPADDRESS` unset.

**Ports:** `8080` web+API (HTTP/LAN) · `12470` web+API (HTTPS) · `11470` direct API · `6881` BitTorrent.

📖 Full ops guide: [`docs/DEVOPS.md`](docs/DEVOPS.md) · TLS deep-dive: [`docs/cert-guide.md`](docs/cert-guide.md).

---

## 🧠 Why it exists

The stock Stremio streaming server is closed-source and, in practice:
- **outbound-only** — it never listens for inbound peers, so you only reach the connectable half of a swarm;
- it **hides the torrent levers** — no real control over piece picking, connectivity, or cache.

This opens it up: **inbound connectivity + playhead-first piece picking** for faster starts and better
reliability on sparse swarms, **plus** hardware transcode for clients that can't direct-play — all in
an image you run yourself. It is **content-neutral infrastructure**: it streams whatever infohash a
Stremio *addon* hands it, and bundles or surfaces nothing.

## 🏗️ Under the hood

One image, two source repos. The runtime image is built **`FROM`** a GPU/ffmpeg base (the companion
fork) and layers the open server on top:

```
┌─────────────── stremio-docker-dual  (companion fork, MIT) ──────────────┐
│ jellyfin-ffmpeg (NVENC/VAAPI) · nginx · bundled Stremio web player        │
└───────────────────────────────▲──────────────────────────────────────────┘
                                 │ FROM
┌─────────────── stremio-libtorrent-server  (this repo) ──────────────────┐
│ FastAPI + libtorrent engine · nginx serves web player + proxies the API   │
│ → one container: web player + open engine on a single origin              │
└────────────────────────────────────────────────────────────────────────────┘
```

Companion fork: **[andrewhack/stremio-docker](https://github.com/andrewhack/stremio-docker)**
(builds the `stremio-docker-dual` image; see its `NVIDIA-GPU.md` for GPU/Proxmox setup).

Modules: `api/` (Stremio HTTP API) · `torrent/` (libtorrent + piece-picker) · `stream/` (Range file
server) · `transcode/` (ffmpeg NVENC/VAAPI → HLS) · `config.py` · `health.py`. Protocol reference:
[`docs/protocol-map.md`](docs/protocol-map.md).

## ✅ Status

All stages shipped and verified on hardware:

| Stage | Scope | State |
|---|---|---|
| 0–1 | Protocol map · FastAPI skeleton · `/health` | ✅ |
| 2 | Torrent core + direct play (inbound peers, head & holes, Range serving, stats) | ✅ |
| 3 | Transcode / HLS (`hlsv2`, NVENC/VAAPI) | ✅ |
| 4 | Subtitles · `opensubHash` · casting | ✅ |
| 5 | Productionise — compose, DEVOPS, healthcheck, AHM | ✅ |
| 6 | All-in-one (web player + engine) · TV-trusted SSL · GPU-optional · Docker Hub | ✅ |

## 🛠️ Development

```bash
uv sync
uv run pytest -q          # unit tests
uv run ruff check .       # lint
uv run uvicorn stremiosrv.app:create_app --factory --host 0.0.0.0 --port 11470
```

## 📜 License & spirit

**MIT** — built on the MIT-licensed [stremio-docker](https://github.com/tsaridas/stremio-docker) fork.

This is **not a commercial product, and we don't monetize it.** It's our contribution to the people
who just want their own open, private streaming server. Use it, share it, make it better. 💛

> Keep it legal: this is neutral infrastructure for content **you** have the right to stream.
