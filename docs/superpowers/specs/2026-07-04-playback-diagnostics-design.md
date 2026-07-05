# Playback Diagnostics — Design / Backlog Spec

**Status:** BACKLOG (future release). Captured 2026-07-04. Not scheduled.

**Goal:** Tell the user, in understandable terms, *why* a torrent isn't playing / is buffering /
is slow — and what to do about it. A ranked list of findings, each with a plain-language
explanation, the evidence it's based on, and a concrete fix/mitigation.

**Tiering (load-bearing):**
- **Free image → deterministic rule engine.** Pure rules over metrics the server already has. On-box,
  offline-safe, content-neutral, **no LLM**. This is the substrate.
- **Supported (paid) image → LLM/chatbot layer** on top of the same structured findings: conversational
  "why won't it play?", follow-ups, guided mitigation. Gated by the **same license/entitlement that
  gates auto-update**, reusing the planned support chatbot (see [[project_stremio_site]] /
  [[project_partner_support]] — LangChain + Ollama + MCP). The diagnostic output becomes an MCP
  tool/resource the chatbot reasons over.

  **Deployment (decided 2026-07-04):** the **chatbot app + MCP servers run in ITCOM infra** (hosted —
  NOT on the appliance box, which only exposes `/diagnose.json`). **LLM inference = Ollama Cloud (Pro
  account)** as primary, with the **own Ollama infra** (local GPU models) also available. The appliance
  stays light; the hosted chatbot pulls the box's diagnostics within the user's authenticated session.

  **Failure isolation (HARD REQUIREMENT):** the LLM must NEVER be able to block the deterministic
  layer. The rule engine (`/diagnose.json` + config-web panel) is the source of truth and has **zero
  dependency** on the LLM/MCP/chatbot/Ollama or any network. If Ollama Cloud is down, the entitlement
  check can't be reached, the MCP is unreachable, or inference times out, the box still returns full
  findings + fixes; even on the paid tier the chatbot **degrades to rendering the raw structured
  findings** (never an error, never a spinner-of-death). The LLM is a presentation/conversation layer
  on top of data that already stands on its own — same pattern as the offline-cert and
  tracker-source fallbacks elsewhere in the project.

This generalizes the existing config-web "Suggestions" advisor, refocused on playback health.

---

## Analytical dimensions — what fast playback actually depends on

The module must reason over **all** of these, not just "seeders + speed". Each is a lever the analyzer
scores independently; buffering is almost always one (or a ranked few) of these, and the value is
telling the user *which*. Ordered by how much they bite on this architecture.

| # | Dimension | What it governs | Signal(s) | Status |
|---|---|---|---|---|
| 1 | **Peer reachability (inbound)** | reach ≠ swarm size — you can only pull from peers you actually connect to; the inbound listener is the project's edge | `inboundPeers`, `portMap`, `num_peers` vs scrape `num_complete` (seeds that EXIST vs peers reached), `connect_candidates` | have (netcheck); **ADD** scrape `num_complete/num_incomplete` for exists-vs-reached |
| 2 | **Piece ordering & buffer lead-time** | getting the *next* bytes in time (continuity) vs max MB/s (throughput); a fast download in the wrong order still stalls | **NEW:** contiguous seconds buffered ahead of the playhead (the adaptive picker already computes contiguous-ahead bytes — **reuse it**), current sequential-mode flag, adaptive engaged / thrashing, `piece_availability()` at the playhead | **NEW** — shared metric with [[the adaptive-piece-picking spec]] |
| 3 | **Startup latency** | the "first few seconds" tax: magnet→metadata, moov/faststart tail-seek, and fast-resume **recheck** after restart | `has_metadata` + time-to-metadata, `torrent_status.state == checking_files` (recheck = the black-first-play case), moov-at-end detection (tail range before playback) | partial; **ADD** checking/recheck state + metadata timing |
| 4 | **Host capacity (CPU / disk / GPU)** | a weak box pegs on piece-hashing + connection mgmt at 20–30 MB/s (the 100%-CPU report), or transcode saturates a core → stalls even with bytes in hand | **NEW:** CPU% / loadavg, hashing+`aio_threads` saturation (via `performance_alert`), disk free + I/O wait, transcode process + GPU util, VAAPI render-node correctness | **NEW** — ties to [[low-CPU profile]] + [[DRM render-node pinning]] backlog items |
| 5 | **Decode path (direct-play vs transcode)** | direct-play = 0 server CPU; transcode makes CPU/GPU the ceiling; silent **software fallback** (wrong render node) spikes CPU with no error | container/codec vs client caps, transcode active?, HW (NVENC/VAAPI) vs SW encoder in use | partial (browser-codec row); **ADD** transcode-fell-back-to-CPU |
| 6 | **Content bitrate (the goalpost)** | "fast enough" is relative to the file — 8 Mbps 1080p vs 80 Mbps 4K remux need wildly different sustained throughput | `ffprobe` required bitrate vs sustained download rate | have (Phase 2) |
| 7 | **Peer discovery** | feeds #1 — you can only reach peers you first *find* (trackers/DHT/LSD/PEX) | `tracker_error_alert` / reply counts, DHT/LSD/PEX enabled, `peer_info.source` mix (how peers were sourced) | partial (tracker-error tap); **ADD** discovery-health finding |

**Key framing for the findings:** #1 and #2 dominate on this stack; #4/#5 decide it on weak boxes; #6
sets the bar. "More seeders" and "faster line" are necessary, not sufficient — the analyzer's job is to
locate which of these seven is the actual constraint and rank it.

---

## Signal inventory

**Already collected (no new plumbing):**
- `GET /stats.json` (top-level): `cache{cacheUsed, cacheSize, diskFree, diskTotal}`,
  `playback{stalls, stallSeconds, timeouts}` (the engine records a stall when `wait_and_read` waits on
  a not-yet-downloaded piece, a timeout when a piece never arrives).
- `GET /{infohash}/stats.json`: `peers`, `swarmSize`, download/upload speed, `progress`,
  `streamProgress`, `streamName`.
- `GET /netcheck.json`: `listenPort`, `peers`, `inboundPeers`, `portMap` (UPnP/NAT-PMP).
- `GET /active.json`: active vs paused torrents + speeds (cross-torrent contention).
- Running config: rate limits, cache size, `idle_download_rate_limit`, `max_streams`, seed policy.

**New taps into libtorrent (small; the engine already runs an alerts loop + holds handles):**
- `torrent_status`: `num_seeds` vs `num_peers`, `connect_candidates`, `num_complete/num_incomplete`
  (tracker scrape = how many seeds exist), `distributed_copies` (availability), `errc`.
- `piece_availability()` — piece rarity, mapped to the playhead region (engine already computes the
  played file / focus / boost, so the playhead→piece mapping exists).
- Alerts to capture: `performance_alert` (libtorrent literally names "download rate limit too low",
  "disk buffer limit reached", "send buffer watermark too low", etc.), `tracker_error_alert`,
  `listen_failed_alert`, `portmap_error_alert`.
- `peer_info` per peer: `flags` (choked / snubbed / interested), `source` (tracker/dht/pex/lsd).
- **Bitrate** (Phase 2): `ffprobe` (already in the image) on the played file → compare required bitrate
  vs sustained throughput = the single most meaningful buffering answer.
- **Buffer lead-time** (dimension 2): contiguous bytes/seconds downloaded ahead of the playhead — the
  adaptive picker already computes contiguous-ahead bytes for its hysteresis, so expose that value
  rather than recomputing it. Low lead-time + healthy download rate = a piece-ordering problem, not a
  bandwidth one (distinguishes "slow line" from "picker fetching out of order").
- **Recheck / startup state** (dimension 3): `torrent_status.state` — `checking_files` during a play =
  the post-restart re-hash (the black-first-play case); `downloading_metadata` = magnet metadata fetch.
  Time-stamp entry into each so "slow to start" is attributed to the right phase.
- **Host stats** (dimension 4): CPU% + loadavg (already surfaced by console-status on the appliance;
  the server can read `/proc/loadavg` / `os.getloadavg()` cheaply), disk free (have), and — Phase 2 —
  whether a transcode is running and on which encoder (HW vs SW). A pegged host + in-hand pieces =
  host-bound, not swarm-bound.

---

## Diagnosis catalog (symptom → distinguishing signal → explanation + fix)

| Symptom | Signal | Explanation → fix |
|---|---|---|
| Won't start, 0% | `has_metadata=false` | "Fetching the file list from peers." → wait / no peer has metadata |
| Won't start, 0% | `swarmSize=0` / scrape `num_complete=0` | "No seeders online." → pick another source/release |
| Slow despite many peers | `download_rate ≈ STREMIOSRV_DOWNLOAD_RATE_LIMIT` | "Capped at ~X kB/s by your rate limit (likely a stale auto-detect)." → raise/clear it |
| Slow, few sending | high `num_peers`, low unchoked, low `upload` | "Cold start — little to trade yet; should climb." → wait / raise upload limit |
| Slow, no inbound | `inboundPeers=0`, `portMap` failed | "Peers can't reach you (no forward / CGNAT) — running outbound-only." → forward BT port / VPN PF |
| Frequent buffering | `download_rate < file bitrate` (Phase 2) | "This file needs ~Y Mbps; your line sustains ~Z." → lower quality / wired / raise cap |
| Frequent buffering | rising `stalls`, low `piece_availability` at playhead | "Waiting on rare pieces at your position." → few seeds; expected on niche content |
| Buffering after a while | `cacheUsed≈cacheSize` + evicting active | "Cache too small — dropping pieces you still need." → raise cache size |
| One stream starves another | 2+ active + `idle_download_rate_limit` engaged | "Another download is competing." → it's throttled / reduce concurrent streams |
| Plays but garbled / browser-only | container/codec (mkv/HEVC) | "This device can't decode this file." → use TV/desktop app (transcode is a separate feature) |
| Black / no progress on first play after a restart | `state == checking_files` | "Re-verifying cached files after a restart — playback starts once it reaches your position." → wait; fast-resume should skip this (flag if it recurs) |
| Slow to start, 0% | `state == downloading_metadata` | "Fetching the file list (piece hashes) from peers/DHT before download can begin." → wait / no peer has metadata yet |
| Downloads fast but still stalls | healthy `download_rate` + low buffer lead-time / thrashing sequential mode | "Bytes are arriving but not in playback order at your position." → picker/adaptive tuning, not a speed problem |
| Stalls with pieces in hand, host pegged | high CPU% / loadavg, `performance_alert` (hashing/disk/buffer) | "The box is CPU/disk-bound at this speed — hashing & serving can't keep up." → lower-CPU profile / fewer connections / faster disk (see host-profile backlog) |
| CPU spikes during a transcoded title | transcode active on **software** encoder (HW not engaged) | "Falling back to CPU transcoding (GPU not used) — spikes CPU, may stall." → fix render-node / GPU passthrough (DRM render-node backlog) |
| Few peers, none arriving | `tracker_error_alert` / DHT disabled / thin `peer_info.source` | "Can't discover peers (tracker errors / DHT off), even though seeds may exist." → check trackers/DHT, add tracker list |

Findings are **confidence-scored and ranked** — buffering is multi-causal, so the value is ranking the
most likely cause from the evidence, not asserting certainty. Uses a **rolling sampler** (like the
advisor) — a 1-frame dip isn't "buffering".

---

## Shape

- **`GET /{infohash}/diagnose.json`** (+ top-level `GET /diagnose.json` for the current stream):
  ranked `[{severity: info|warn|critical, title, plain, evidence:{…}, fix, confidence}]`. Pure rule
  engine → unit-testable, content-neutral (reports *your* stream's health, like a download manager).
- **config-web "Playback health / Why isn't it playing?" panel** (extends the Suggestions card).
- Optionally exposed to a Stremio addon/overlay so the *reason* shows during buffering instead of a
  blank spinner.
- **Paid:** the chatbot calls `/diagnose.json` as an MCP tool → conversational diagnosis + guided fixes.

---

## Phasing

- **Phase 1 (small, high value):** rule engine over the *existing* endpoints + cheap `torrent_status`
  reads — rate-cap, no-seeds, no-inbound, cold-start, cache-thrash, contention, stall-rate, plus the
  cheap new dimensions: **recheck/metadata startup state** (dim 3), **buffer lead-time** (dim 2, reuse
  the adaptive picker's contiguous-ahead value), **host CPU/loadavg** (dim 4, `os.getloadavg()`).
  ~90% of real complaints, no new libtorrent plumbing. Free tier ships here.
- **Phase 2:** capture `performance_alert` + `tracker_error` in the alerts loop (dim 4 host-bound, dim 7
  discovery); add bitrate-vs-throughput via `ffprobe` (dim 6); piece-rarity-at-playhead (dim 2); scrape
  `num_complete` exists-vs-reached (dim 1); transcode HW-vs-SW encoder detection (dim 5).
- **Phase 3 (paid):** wire the findings into the support chatbot as an MCP tool (entitlement-gated).

---

## Open questions

1. ~~Where the LLM runs~~ **SETTLED (2026-07-04):** chatbot + MCP in ITCOM infra; LLM = Ollama Cloud
   (Pro) primary + own Ollama infra; box only exposes `/diagnose.json`. See Deployment above.
2. **Privacy / content-neutrality of the paid path — sharper now that Ollama Cloud is external.**
   `/diagnose.json` carries stream metadata (infohash, name). Ollama **Cloud** is a third party, so
   content-bearing fields must NOT go to it raw: send **metrics-only** (strip title/infohash) to the
   cloud model, and route any content-bearing reasoning only through the **own Ollama infra** (local),
   or keep it strictly inside the user's authenticated session. Per-customer scoping stays enforced in
   the MCP/tool layer, never by trusting the LLM (the partner-support rule).
3. **Free tier stays fully offline** — no phone-home; the rule engine and panel work with no network.
