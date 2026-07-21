# CLAIRE Azure Forensic Technical Report

**Scope:** Read-only forensic audit of the live `clairesystems.ai` deployment.
**Host confirmed:** This investigation was run directly on the production host (hostname `clairetemp`, Azure/Hyper-V VM, Ubuntu 24.04.4 LTS) that terminates `clairesystems.ai` via nginx with a live Let's Encrypt certificate. All findings below marked "verified live" were obtained by inspecting running processes, systemd units, nginx config, and by issuing read-only HTTP requests against the running services (`curl`, no state-changing calls). Findings marked "code only" come from static inspection of the repository at `/home/LuciusPrime/claire` and were not exercised live.
**No files were modified. No services were restarted. No secrets were printed.**

---

## Answers up front

**1. Is CLAIRE currently a functioning control plane, or mainly a demonstration interface?**
Both, unevenly. There is one real, wired governance path — `ClaireRuntime.handle_user_message()` in `claire_runtime.py`, invoked from `/reply` in `claire_gui.py` — that genuinely runs classification, authority checks, memory recall, model invocation, output validation, and a cryptographically chained Truth Spine on every non-demo request. But the same file also contains a parallel, much larger surface of **demo-labeled paths** (`demo=true&demo_scenario=...`) that return canned/synthetic payloads via `build_governed_demo_payload()`, and a workflow-debug HUD where 27 of 28 `machineCalled` values in the front-end are **hardcoded string literals**, not derived from server responses. The public demo experience is mostly a demonstration interface with a real engine underneath it that isn't consistently exposed to the UI.

**2. Can the existing deployment become a commercial governance API without a full rewrite?**
Yes, directionally — the hard part (a real, cryptographically-chained, multi-stage governance pipeline with an audit trail) already exists in `claire_runtime.py` / `claire_runtime_truth.py` and works. But it is currently welded to one FastAPI monolith (`claire_gui.py`, ~17,000 lines) serving HTML, demo endpoints, and the governance path from the same process, with no API-key auth, no tenant model, no versioned contract, and one unbounded blocking call (`fcntl.flock`, see below) sitting in the hot path. This is a consolidation and extraction job, not a from-scratch build — but it is not a trivial one either.

**3. What are the three most important broken connections?**
- **`fcntl.flock(fh.fileno(), fcntl.LOCK_EX)` at `claire_runtime_truth.py:130`** — a real, unbounded, no-timeout blocking lock hit ~22 times per turn, on the same shared file, from every request through the governed path. This is the most credible root cause for the "Voice captured... waiting for turn completion" / "Stream quiet. Holding latest text..." stall.
- **The `/status` health cards are a mix of real and fake checks in one payload.** `truth_spine` and `temporal_engine` call real runtime objects; `are`, `llm`, `ingest`, `spectacle` are `subprocess.check_output("ss -tulnp | grep <port>")` calls that only prove *something* is listening on a port — and the `llm` check greps port **8080**, which is the Go reasoning backend, not either of the two actual model servers (llama.cpp on 8091/8092). "LLM ONLINE" can be true while both real model servers are down.
- **The workflow-debug HUD (`Control Layer`, `Machine Called`, `Trace ID`) is mostly decorative.** `machineCalled: "NO"` is a literal string baked into 27 of 28 call sites in the client JS, regardless of what the server actually did. It is not a governance signal; it's UI copy.

**4. What is the fastest credible commercial demo?**
A side-by-side "same model, same document, same question" run: Run A hits the local llama.cpp model directly (bypassing `claire_runtime.py`) and produces an unsupported/unauthorized answer; Run B sends the identical prompt through `/reply` (non-demo) and shows Sentinel/authority denial, or a Truth Spine-sealed, trace-replayable answer. All the pieces for Run B already exist and run today; Run A requires nothing new (the local model is already reachable). This is UI and script work, not new governance engineering. See Phase 16 for detail.

**5. What is the minimum technical work required before showing this to an investor or pilot customer?**
Fix the `flock` timeout (or replace with a bounded lock), stop showing the demo-scenario HUD as if it were live governance telemetry (either wire `machineCalled`/`controlLayer` to real response data or remove them from demo paths), fix the `llm` status check to point at the actual model servers, and put the `/reply` non-demo path behind at minimum one working end-to-end scripted demo you've personally run and watched fail closed. All four are days, not months, of work — see Phase 17.

---

## 1. Executive Summary

CLAIRE's live deployment is a single Azure VM (`clairetemp`) running nine `systemd`-managed application processes, six Dockerized data services, two llama.cpp model servers, and nginx as the TLS-terminating reverse proxy for `clairesystems.ai`. The center of gravity is `claire_gui.py`, a ~17,000-line FastAPI application that serves the public HTML/JS front end, ~47 backend routes, and hosts the one real governance engine on the system: `ClaireRuntime.handle_user_message()` in `claire_runtime.py` (2,262 lines), which wires together a Truth Spine (`claire_runtime_truth.py`), Gyro orientation, 3CRP admission/routing gates, ARE-derived memory recall, Recognition Rail, Q Insight, EchoShield, and a Sentinel memory-write gate — and which is genuinely invoked on every non-demo `/reply` call.

Three of the specific symptoms named in the brief were investigated to ground truth:
- **The Veritas Legal 404** is **not currently reproducible**. nginx was missing a `location` block for `/veritas-legal/` until a config change was made and reloaded on **2026-07-19 09:17:39 UTC** (a backup of the prior config, `claire.before_veritas_legal_20260719_090921`, is still sitting next to the live one). Live `curl` tests against both the public domain and the backend directly now return `HTTP 200` with valid JSON. This was very likely a real bug that has since been fixed at the infrastructure level.
- **The "[STATUS ERROR] Failed to fetch" messages** trace to a specific, identified function (`checkStatus()`, polling `/status` every 5 seconds, `claire_gui.py:6802-6829`). `/status` currently returns `200` both through nginx and directly. "Failed to fetch" is a browser network-layer error (not an HTTP error code), so this is consistent with a transient backend outage or restart window, not a permanently broken route — but several *other* routes the backend defines (`/truth-spine/status`, `/are-spectacle`, `/scholar`, `/privacy`, `/terms`, `/support`, `/office/*`) are confirmed, live, currently returning nginx's own 404 HTML because nginx has no location block for them at all.
- **The status "ONLINE"/"READY" cards** are a genuine mix: `truth_spine` and `temporal_engine` call real, live runtime objects; `are`, `llm`, `ingest`, `spectacle` are shell-outs to `ss -tulnp | grep <port>` that only prove a process is bound to a port, and the `llm` check is bound to the *wrong* port (the Go backend, not the model servers).

## 2. Bottom-Line Assessment

CLAIRE is closer to a commercial governance product than its public demo surface suggests, because the governance engine is real and already running in production — but the repository also contains several **parallel, divergent implementations of the same named components** (three different classes are all called `AREStore`; two different Truth Spine implementations exist; a `Lycanthrope` overwatch class exists but is never instantiated anywhere in the live request path). None of this is fatal, but it means "expose the existing system" is not a pure plumbing task — it requires first deciding, component by component, which of the 2-3 existing implementations is canonical, and formally retiring the others. That decision work, not new invention, is the dominant cost between here and a sellable API.

## 3. Live Deployment Inventory (Phase 1)

**Verified live**, via `hostnamectl`, `ss`, `ps`, `systemctl`, `docker ps`, and direct file reads.

| Item | Value |
|---|---|
| Hostname | `clairetemp` |
| Cloud | Microsoft Azure, Hyper-V virtualization (`hostnamectl`: `Virtualization: microsoft`) |
| OS | Ubuntu 24.04.4 LTS, kernel `6.17.0-1011-azure` |
| Repo path | `/home/LuciusPrime/claire` |
| Git branch | `main` |
| Latest commit | `26b0455dac30dc0319913df421bd17ea41b5df9b` — "Add Hugging Face post deploy smoke checks" (2026-07-19 05:40:16 UTC) |
| Uncommitted changes | **70 untracked/modified paths** at time of audit (`git status --porcelain`), mostly new top-level `.md` audit/report documents and some new scratch modules (`claire_vde/*`, `claire_state/sentinel/`) — see git status snapshot in system context. No core runtime `.py` file (`claire_gui.py`, `claire_runtime.py`, `claire_runtime_truth.py`) shows as modified/untracked; those are clean and committed. |
| Python | 3.12.3 (both system and `/home/LuciusPrime/claire/venv`) |
| Node/npm | v18.19.1 / 9.2.0 (present, not confirmed in active use by the live services below) |
| Virtualenvs | `/home/LuciusPrime/claire/venv` (159 packages installed), separate `venv` under `/home/LuciusPrime/are-spectacle-v2/venv` |
| Docker | Active (`systemctl is-active docker` → active) |
| Docker Compose | Not directly confirmed; containers below were started with `claire-*` project-prefixed names consistent with Compose |
| Process manager | `systemd` (no supervisord — checked, inactive/absent) |
| Reverse proxy | nginx, active since 2026-06-24 06:44:13 UTC, config last reloaded 2026-07-19 09:17:39 UTC |
| TLS | Let's Encrypt, `clairesystems.ai` + `www.clairesystems.ai`, ECDSA, **valid, expires 2026-09-17** (58 days from audit date) |
| Domain routing | nginx `server_name clairesystems.ai www.clairesystems.ai`, HTTP→HTTPS redirect on port 80, HTTPS on 443 |

### systemd services (all `claire-*`, verified via `systemctl list-units`)

| Service | State | Purpose (per unit description) |
|---|---|---|
| `claire-are.service` | active/running | Claire ARE Memory Server |
| `claire-go.service` | active/running | Claire Go Reasoning Backend |
| `claire-gui.service` | active/running | Claire Public GUI |
| `claire-ingest.service` | active/running | Claire Parser/Sentinel Ingest Bridge |
| `claire-llama.service` | active/running | Claire Local Llama Server |
| `claire-sidecar-health.service` | inactive (dead) | Sidecar Health Snapshot Logger — **timer-triggered oneshot**, ran and exited cleanly 15s before this check; not broken, just idle between timer fires |
| `claire-veritas-legal.service` | active/running | Claire Veritas Legal API |
| `claire-veritas-llama.service` | active/running | Claire Veritas Qwen3-14B Llama Server |
| `claire-veritas-mobile.service` | active/running | Claire Veritas Mobile GUI |

`claire-gui.service` unit file (`/etc/systemd/system/claire-gui.service`): `ExecStart=/home/LuciusPrime/claire/venv/bin/uvicorn claire_gui:app --host 0.0.0.0 --port 8000`, `Restart=always`, `RestartSec=5`, logs to `/home/LuciusPrime/claire/gui.log`. A drop-in (`claire-gui.service.d/nemo-guardrails.conf`) sets `CLAIRE_NEMO_GUARDRAILS=1`. **This process has been running continuously since 2026-07-17 00:16:25 UTC — it has not picked up any `claire_gui.py` source changes committed after that timestamp** (the file on disk was last modified 2026-07-19 04:50:13 UTC, ~2.5 days after the running process started; uvicorn does not hot-reload). This is a general staleness risk, independent of the specific Veritas fix discussed in Phase 8.

### Listening ports / processes (verified via `ss -tlnp` + `/proc/<pid>/cmdline`)

| Port | Bind | Process | Identity |
|---|---|---|---|
| 80, 443 | `0.0.0.0` | nginx | TLS termination, reverse proxy |
| 8000 | `0.0.0.0` | uvicorn (pid 1853658) | `claire_gui:app` — main public GUI, started Jul 17 |
| 8011 | `0.0.0.0` | uvicorn (pid 1759031) | `claire_gui:app` — **second instance of the same module**, serves `/veritas-mobile*`, started Jul 16 |
| 8002 | `127.0.0.1` | uvicorn (pid 1323351) | `ARE_SERVER:app`, cwd `/home/LuciusPrime/claire` |
| 8081 | `127.0.0.1` | uvicorn (pid 1323353) | `claire_ingest_bridge:app` |
| 8010 | `127.0.0.1` | uvicorn (pid 1323350) | `app.main:app`, cwd `/home/LuciusPrime/are-spectacle-v2` — a **separate repository/venv** from `/home/LuciusPrime/claire` |
| 8020 | `0.0.0.0` | python (pid 2069440) | `web.app:app`, cwd `/home/LuciusPrime/claire_repos/claire-veritas-legal` — the **dedicated** Veritas Legal service (also a separate repo checkout) |
| 8030 | `0.0.0.0` | Docker container `claire-venture-api-1` | `uvicorn claire_vde.api:app`, containerized |
| 8080 | `127.0.0.1` | Go binary (pid 1759058, `/tmp/go-build.../main`) | "Go Reasoning Backend" (`claire-go.service`) — **built to a `/tmp` path**, i.e. its binary is not a stable, versioned build artifact in the repo |
| 8091, 8092 | `127.0.0.1` | `llama-server` (llama.cpp) | Two local model servers: Qwen3.5-9B (8091) and Qwen3-14B (8092), context 8192, `-ngl 0` (CPU-only inference) |
| 5433 | `0.0.0.0` | Docker `claire-postgres-1` | `postgres:16` |
| 6380 | `0.0.0.0` | Docker `claire-redis-1` | `redis:7` |
| 6333 | `0.0.0.0` | Docker `claire-qdrant-1` | `qdrant/qdrant:latest` — vector DB |
| 7474, 7687 | `0.0.0.0` | Docker `claire-neo4j-1` | `neo4j:5` — graph DB |
| 9000, 9001 | `0.0.0.0` | Docker `claire-minio-1` | `minio/minio:latest` — S3-compatible object storage |
| 5678 | `127.0.0.1` | Docker `claire-n8n` | `n8n` workflow automation, running 2 months |

**Important finding:** Postgres, Redis, Qdrant, Neo4j, and MinIO are all running, healthy, and have been up for 8 days — but a repo-wide grep of `claire_gui.py`, `claire_runtime.py`, `claire_runtime_truth.py`, `are_memory_store.py`, and `trace_logger.py` for their ports/names (`5433`, `6380`, `6333`, `neo4j`, `qdrant`, `minio`, `:5432`, `:6379`) returned **zero matches**. These five data services are not currently wired into the live chat/governance request path at all. They may belong to the `claire_vde` venture-engine subsystem (the Postgres/Redis pairing is a common venture-API dependency) rather than to CLAIRE's core governance/memory system, which — per this session's earlier tracing — actually persists to flat JSONL files and SQLite, not any of these five services. This should be confirmed with whoever owns `claire_vde` before assuming they're available capacity for a SaaS gateway's storage layer.

### Storage, logs, env files (verified via `ls`/`du`)

- Data directories: `/home/LuciusPrime/claire/data` (108M), `/home/LuciusPrime/claire/claire_state` (1.8M).
- Env files present (names only, not read): `.env`, `.env.example`, `.env.venture.example`, `hf_claire_runtime_full/.env.example`, `hf_space/.env.example`.
- Logs at repo root include `gui.log` (1.0M, actively written — matches `claire-gui.service`'s `StandardOutput`), `are.log` (3.9M), `ingest.log` (6.9M, owned by `root`, not `LuciusPrime` — worth checking who/what writes as root), `go.log` (68M — largest log on the box), `llama.log`, plus several **stale, zero-byte or long-untouched logs** (`gui_8011.log` 0 bytes since Jul 16, `gui_preview_8028.log` 0 bytes since Jul 15, `claire_ui.log`/`server.log`/`proxy.log` last touched April 14) — these are dead artifacts from earlier deployment iterations, not active signal.
- Deployment/bootstrap scripts at repo root (10 found): `LAUNCH.sh`, `claire_pulse_final.sh`, `run_are.sh`, `setup_venv.sh`, `claire_sovereign_boot.sh`, `claire_bootstrap.sh`, `claire_double_pulse.sh`, `bootstrap.sh`, `boot_claire.sh`, `claire_bootstrap_v2.sh`. The number and naming overlap (three separate "bootstrap" variants, two "pulse" variants) is itself evidence of iterative, non-consolidated deployment tooling — contents not individually audited in this pass.

## 4. Repository Architecture Map (Phase 2)

This repo is very large (17,000+ line primary file, hundreds of top-level Python modules, several nested sub-repos). Rather than a full tree dump, here is the map of files that actually matter to the live request path, established through direct tracing this session:

```
/home/LuciusPrime/claire/
├── claire_gui.py              # PRIMARY BACKEND ENTRY POINT (FastAPI, ~17k lines).
│                               # Serves HTML/JS front end, ~47 backend routes, hosts
│                               # the governed /reply path and ~30 demo/utility routes
│                               # in the SAME process and file.
├── claire_runtime.py          # THE real governance engine. class ClaireRuntime,
│                               # method handle_user_message() (line 111-890) — wires
│                               # 3CRP, Gyro, ARE recall, Recognition Rail, Q Insight,
│                               # EchoShield, Sentinel, Truth Spine into one sequential
│                               # per-turn pipeline. Instantiated once at claire_gui.py:171.
├── claire_runtime_truth.py    # RuntimeTruthSpine — the Truth Spine actually used live.
│                               # Hash-chained JSONL append log with HMAC signing
│                               # (TrailLinkSigner). Contains the flock-with-no-timeout
│                               # call at line 130 (see Phase 9).
├── nemotron_adapter.py        # Model adapter: NVIDIA NIM API (remote) with a local
│                               # llama.cpp HTTP bridge fallback. Both paths have
│                               # explicit timeouts.
├── original_are_bridge.py     # Reimplements the *format* of the original AREStore's
│                               # JSONL records, but does NOT import or call the real
│                               # AREStore class. This is what's actually wired in.
├── faiss_are_index.py         # FaissAREIndex — vector/embedding search over ARE JSONL
│                               # records. A distinct, additional lineage from AREStore.
├── are_memory_store.py        # AREMemoryStore — a THIRD, unrelated, SQLite-backed
│                               # memory implementation. Not instantiated in the live
│                               # ClaireRuntime() (defaults to memory_store=None).
├── claire_are/core.py         # A fourth AREStore-named class — Truth-Spine-based,
│                               # not used by claire_runtime.py.
├── claire_core/adapters/lycanthrope.py  # Lycanthrope overwatch class — a static
│                               # mode/permission matrix, no threads/async/loop. Never
│                               # instantiated anywhere in claire_runtime.py.
├── trace_logger.py            # TraceLogger — separate SQLite + JSONL trace log,
│                               # called once per turn unconditionally.
├── temporal_engine.py         # TemporalEngine — added 2026-07-18, heavily wired into
│                               # every turn (session/turn timing, relative-time
│                               # resolution). No blocking calls found inside it.
├── veritas_adapter.py         # Local status-only functions for the Veritas
│                               # trading-station subsystem (no network calls).
├── claire_courtlistener.py    # Real HTTP client for CourtListener, with explicit
│                               # timeouts (30s/20s).
└── claire_vde/                # Separate "venture" subsystem — own API, own Docker
                                # container (claire-venture-api, port 8030). Not
                                # reachable from grep for shared Postgres/Redis usage
                                # with the core app.

/home/LuciusPrime/claire_repos/claire-veritas-legal/   # SEPARATE git checkout, own
                                # `web/app.py` FastAPI app (port 8020, 30+ routes:
                                # /chat, /search, /courtlistener/*, /edgar/*, /ocr,
                                # /ingest...). This is the "real" dedicated Veritas
                                # Legal service — distinct from the /veritas-legal/run
                                # route that also exists inside claire_gui.py.

/home/LuciusPrime/are-spectacle-v2/                    # SEPARATE repo/venv, port 8010,
                                # `/are-spectacle` route in claire_gui.py exists but is
                                # not currently reachable via nginx (see Phase 5).
```

**Obsolete/duplicate implementations identified this session:** three additional `AREStore`-named classes beyond the true original (`veritas/veritas_trader_engine.py:505-616`, `claire_are/core.py`, and the conceptually-related-but-differently-named `AREMemoryStore`/`FaissAREIndex`); two Truth Spine implementations (`claire_runtime_truth.py` live, `claire_are/truth_spine.py` unused by the live path); the true original 70-line `AREStore` itself lives entirely outside this repo at `/home/LuciusPrime/original_are.pyiginal_are.py/are.py` and is imported by nothing.

**Code referenced by the UI but not connected to the runtime:** `bare_role`/`fare_role` fields referenced in demo-report-building JS (`claire_gui.py` — `build_demo_report_markdown`, `ooda_demo_artifacts`) do not exist anywhere in `claire/runtime/gyro.py`, the actual Gyro module used by `handle_user_message`. BARE and FARE are demo narrative text, not implemented pipeline stages, in the live governed path.

## 5. Current Request Flow (Phase 3)

Traced this session, browser to response, for the two request types the brief called out:

**A. Voice/mic path (the reported stuck-turn symptom):**
`recognition.onresult` (`claire_gui.py:4191`) fires on every final speech fragment → renders "Voice captured... Claire is waiting for turn completion" (`:4209`) → either an explicit "over" triggers `commitTurn()` immediately, or `scheduleLongSilenceCommit()` waits. `commitTurn()` (`:6298`) → `dispatchCommittedTurn()` (`:6337`) → POST to `/reply` with `stream:true` → server-side `_reply_stream_response()` (`:14893`) sends an ndjson `start` event, then runs the **entire** `build_reply()` → `ClaireRuntime.handle_user_message()` synchronously inside `asyncio.to_thread`, and only emits `meta`/`chunk`/`done` events *after* that full call returns. There is no true token streaming — the client fakes it by chunking the finished answer. The client's `startStreamStallTimer()` (`:4909`) just relabels the status text `"Stream quiet. Holding latest text..."` every 3s past an 18s gap; it never aborts or retries. If `handle_user_message()` hangs — most plausibly on the unbounded `fcntl.flock` — the turn never resolves, matching the reported symptom exactly.

**B. Idle/demo HUD path (the "Lane: public_demo, Control Layer: NO, Machine Called: NO, Trace ID: NONE" screenshot):**
This is **not a live request at all**. `claire_gui.py:5874-5881` sets exactly this debug object (`route: "idle"`, `lane: "public_demo"`, `controlLayer: "NO"`, `machineCalled: "NO"`, `traceId: "NONE"`) unconditionally when the workspace is cleared/reset — i.e., it's the intentional pre-request idle display, not a routing bug, bypass, or failed call. Separately and more concerning: **27 of 28** other `machineCalled:` assignments across the entire client JS are the hardcoded literal `"NO"`, including inside flows (`memory_performance_visual`, `/veritas-legal/run` invocation, `/tts`, `/diagnostic`) where a real backend call *does* happen. Only one call site (`claire_gui.py:6533`, Drive integration) sets it dynamically (`data.connected ? "YES" : "NO"`). **Conclusion: "Machine Called: NO" in a screenshot is not evidence that no model/tool ran — it is nearly always just the constant the JS was written to display.** This is a genuine, verifiable UI defect (the HUD misrepresents server-side reality), separate from the actual governance pipeline's correctness.

Module execution status inside `handle_user_message()` (established via full line-by-line trace earlier this session, `claire_runtime.py:111-890`):
- **Always executed, in this order:** input normalize → Diode redact/secret-scan → TemporalEngine session/turn start → 3CRP ingress admit → preliminary lane routing → lane resolution → risk gate → HandshakeBroker authority (`traillink.authentication` event) → current-truth load → memory eligibility → **Gyro orientation** → (stability gate, may short-circuit) → ARE/FAISS memory recall → **Recognition Rail** → **Q Insight** → temporal policy gate → post-Gyro 3CRP authorization (may short-circuit) → context packet build → model authorization → **model call** (`call_nemotron`) → answer sanitize/redact → LoopbackLayer post-check → **response validation** (`sentinel_validator.validate_response`) → EchoShield classification → **Sentinel memory-write authorization** → 3CRP memory-write gate → conditional memory commit → 3CRP egress authorization → `output.released` event → `runtime_truth.seal_turn()` → trace log write → return.
- **Conditionally executed:** demo mode short-circuits to a separate handler entirely (`handle_demo_message`); Veritas/CourtListener subsystem status only for their specific lanes; visible debug payload only if requested and non-guest.
- **Reordered relative to the architecture given in the brief:** Gyro runs *before* Recognition Rail, Veritas parsing, and Q Insight, not after them as the intended order states. There is no distinct "Veritas parser/normalization/provenance" stage at all — input normalization is a one-line whitespace collapse (`claire_runtime.py:1442-1443`); Veritas only appears later, conditionally, for trading-lane status display.
- **Bypassed/never called in this method:** Lycanthrope (zero references anywhere in `claire_runtime.py`).
- **Not a distinct stage, contrary to its name suggesting otherwise:** "3CRP ROUTING" appears as a second-pass authorization (`3crp.post_gyro_authorization`) but authority/lane resolution actually happened earlier, before Gyro — so the "first pass vs second pass" framing in the intended architecture doesn't cleanly match the code's actual gating order.

## 6. Governed vs. Ungoverned Paths (Phase 4)

`memory_performance_visual` is **not a backend route**. It is a client-side display label (`claire_gui.py:5283`, `:5968`) set after calling `/reply?q=...&demo=true&demo_scenario=memory_speed`. The server-side handler for `demo=true` (non-machine-key queries) is `build_governed_demo_payload()` (`claire_gui.py:12762`) — a **separate function from `ClaireRuntime.handle_user_message()`**. This needs one more confirmation this audit did not complete: whether `build_governed_demo_payload` synthesizes its narrative from static/canned content or actually calls into `ClaireRuntime` internally for the trace_id/summary fields it returns. What is confirmed: the trace_id shown in this demo path is real in the sense that it's generated and can be fetched back via `/trace/{trace_id}` (`claire_gui.py:14979`), and `Control Layer: YES` is a hardcoded constant at the call site, not a computed value — so its presence doesn't by itself prove the 3CRP pipeline ran.

Side-by-side, what's actually different between "governed" and "ungoverned" paths on this system:

| | Non-demo `/reply` (governed) | Demo `/reply?demo=true` | Direct model access (bypass) |
|---|---|---|---|
| Entry | `claire_gui.py:14955` `reply_post` | Same route, `demo_bool` branch at `:14846` | e.g. curling `llama-server` on 8091/8092 directly (only reachable on `127.0.0.1`, not exposed via nginx) |
| Handler | `ClaireRuntime.handle_user_message()` | `build_governed_demo_payload()` | none |
| Truth Spine sealed | Yes, `seal_turn()` at `:787` | Not confirmed this pass | No |
| Authority/Sentinel gates | Yes | Not confirmed this pass | No |
| Trace replayable | Yes, `/trace/{trace_id}` backed by SQLite + JSONL | Partially — `_public_demo_fetch_trace` uses a separate SQLite (`public_demo.sqlite`) | No |

## 7. API Route Inventory (Phase 5)

`claire_gui.py` defines **47** `@app.*` routes (grep-verified). nginx (`/etc/nginx/sites-enabled/claire`) explicitly proxies a much smaller subset. Cross-referencing the two, live-tested against the public domain via loopback+Host header:

| Route (backend, port 8000 unless noted) | nginx exposes it? | Live test result |
|---|---|---|
| `/`, `/health`, `/status`, `/are-demo`, `/are-demo/*`, `/ask`, `/reply`, `/reply-stream`, `/upload`, `/upload-folder`, `/diagnostic`, `/drive/*`, `/tts`, `/claire/query`, `/trace/{id}` (regex), `/static/*` | Yes | `/status` → **200** (verified live) |
| `/veritas` → `/veritas/*` (port 8020) | Yes | not re-tested this pass |
| `/veritas-legal/*` → port 8000 | Yes, since 2026-07-19 09:17 UTC | **200, valid JSON** (verified live, both via nginx and direct) |
| `/veritas-mobile`, `/veritas-mobile/api/*` (port 8011) | Yes | not re-tested this pass |
| `/veritas-legacy/*` → port 8020 | Yes | not re-tested this pass |
| `/machine/*` | nginx **blocks with 403** before reaching backend | Intentional-looking security boundary — matches the "Machine Called" theme; worth confirming with whoever set this rule that it's deliberate policy and not an accidental block of something meant to be reachable |
| `/action` | nginx **blocks with 403** | Same as above |
| `/truth-spine/status` | **No nginx location — falls to catch-all `return 404`** | **404 via nginx (verified live), 200 direct to backend (verified live)** |
| `/are-spectacle` | **No nginx location** | **404 via nginx (verified live)**, works direct |
| `/scholar` | **No nginx location** | **404 via nginx (verified live)** |
| `/privacy`, `/terms`, `/support` | **No nginx location** | Not individually re-tested, same code path as `/scholar` — expect 404 |
| `/office/ad-draft`, `/office/tasks`, `/office/task/{id}` | **No nginx location** | Expect 404 by same logic, not individually tested |
| `/report/{trace_id}` | **No nginx location** (only `/trace/` regex is exposed, `/report/` is not) | Expect 404, not individually tested |
| `/courtlistener/open` | **No nginx location** | Expect 404, not individually tested |

**Frontend calls to routes that don't exist as distinct backend endpoints:** none found — every `safeJsonFetch`/`fetch` call in the client JS (`/tts`, `/action`, `/trace/{id}`, `/reply`, `/drive/research`, `/veritas-legal/run`, `/diagnostic`, `/status`) has a matching backend route. The gap is entirely on the nginx-exposure side, not the frontend-calling side — the frontend simply doesn't call the routes that are exposed-in-code-but-not-in-nginx (`/are-spectacle`, `/scholar`, `/truth-spine/status`, etc.), so users never hit this class of bug through normal navigation; it would only surface if something (a bookmark, an old build, a direct link, a monitoring probe) tried to reach those paths directly.

## 8. Veritas 404 Root Cause (Phase 6)

**This is resolved, not currently broken.** Exact evidence:

- `git blame` on `claire_gui.py`: `@app.post("/veritas-legal/run")` (line 15823) was added **2026-07-08 15:56:30 UTC**, commit `a126999`.
- `/etc/nginx/sites-enabled/claire.before_veritas_legal_20260719_090921` is a preserved backup of the nginx config **without** any `location` block for `/veritas-legal/`.
- `diff` between that backup and the live config shows exactly one addition: a `location ^~ /veritas-legal/ { proxy_pass http://127.0.0.1:8000; ... }` block.
- nginx was reloaded at **2026-07-19 09:17:39 UTC** (confirmed via `journalctl -u nginx`), immediately after that config edit.
- Live test now: `curl -X POST https://.../veritas-legal/run` (via nginx, Host header) → `HTTP 200`, valid JSON. Direct to backend port 8000 → also `200`.

**Root cause, precisely stated:** before 2026-07-19 09:17 UTC, nginx had no `location` rule matching `/veritas-legal/*` at all, so any request to it fell through to the config's final catch-all, `location / { return 404; }` (`claire` config, near the bottom) — which is nginx's own hardcoded 404, served as HTML, without ever reaching any backend. This exactly matches "expected JSON, got nginx 404 HTML": the backend route existed and worked the whole time (since July 8); nginx simply never routed to it. Someone has since added the missing `location` block and reloaded nginx. **No code fix is needed. No further action is needed on this specific item** unless the fix itself needs verifying against a load balancer or CDN layer outside this VM (not investigated — see Open Questions).

## 9. Status Fetch Failure Root Cause (Phase 7)

`checkStatus()` (`claire_gui.py:6802-6829`) calls `safeJsonFetch("/status")` on page load and every 5000ms via `setInterval`. On any failure it writes `"[STATUS ERROR] " + err.message` to the on-page log. `/status` currently returns `200` reliably (verified live, both via nginx and direct-to-backend). Since "Failed to fetch" is the literal message the browser `fetch()` API throws for network-layer failures (DNS, connection refused, CORS, mixed content) rather than an HTTP status code, and the route works right now, the most likely explanations — not independently confirmed this pass — are: (a) the screenshot was taken during a `claire-gui.service` restart/outage window (the unit is `Restart=always`/`RestartSec=5`, so brief gaps are possible and would produce exactly this symptom for ~5-10s at a time), or (b) a client-side network condition specific to that browser session. **No CORS misconfiguration, wrong hostname, or missing route was found for `/status` itself.**

What *is* confirmed broken and would independently produce "Failed to fetch"-style symptoms for anyone whose UI (or monitoring, or a stale cached bundle) calls the unexposed routes: `/truth-spine/status`, `/are-spectacle`, `/scholar`, etc. (see Phase 7 table above) all currently 404 through nginx. If any dashboard variant calls `/truth-spine/status` directly instead of reading `truth_spine` off the `/status` payload, that call would fail consistently, not transiently.

**Trustworthiness of the status cards themselves** (`/status` handler, `claire_gui.py:16721-16804`, read in full this session):
- `are`, `llm`, `ingest`, `spectacle` — each is `subprocess.check_output("ss -tulnp | grep <port>")`, i.e., "is a process listening on this port," not a functional health check. **`llm` checks port 8080, which is the Go reasoning backend (`claire-go.service`), not either llama.cpp model server (8091/8092).** A status of `"llm": "ONLINE"` does not mean a model is reachable.
- `voice` — calls a dedicated `voice_runtime_status()` function (`claire_gui.py:16255`), not inspected in detail this pass but structurally more meaningful than a bare port grep.
- `gemini` — derived from `is_gemini_available()` (`claire_gui.py:13137`) plus a `LAST_GEMINI_ERROR` global; not confirmed this pass whether "available" means "API key present" or "last call succeeded" — flagged as an open question, since "GEMINI READY" meaning only "a key is configured" versus "the API is currently reachable" is exactly the kind of gap the brief warned against assuming away.
- `truth_spine` — **calls the real `RuntimeTruthSpine.verify()`**, which re-walks the entire hash chain and checks signatures (see this session's earlier trace of `claire_runtime_truth.py:204-253`). This is a genuine, non-trivial live check.
- `temporal_engine` — **calls the real `TemporalEngine.status()`** on the live singleton. Also genuine.
- `claire_core` — dynamically imports `claire_core.runtime.health.core_health()`; not inspected this pass.

**Bottom line: `truth_spine` and `temporal_engine` are trustworthy status signals. `are`, `llm`, `ingest`, and `spectacle` are not — they can show "ONLINE" while the thing a user actually cares about (can this service answer a question) is down, and `llm` in particular is watching the wrong service entirely.**

## 10. CLAIRE Module Reality Matrix (Phase 8)

Statuses are assigned only from code/runtime evidence gathered this session (this session included a full line-by-line trace of `handle_user_message`, not just a name search).

| Component | Status | Evidence |
|---|---|---|
| **ARE** (memory) | **CONNECTED BUT LIMITED** | The true original `AREStore` (`/home/LuciusPrime/original_are.pyiginal_are.py/are.py`, 70 lines) is never imported anywhere in this repo — dead code, outside the repo entirely. What's actually wired into `ClaireRuntime` is `original_are_bridge.py` (a reimplementation of the JSONL record format, no watchdog/trim logic) plus `faiss_are_index.py` for vector search. Called live at `claire_runtime.py:344-384` (`are.consulted` event), confirmed in trace. |
| **GO** (reasoning backend) | **UNKNOWN — not code-audited this pass** | Confirmed running (`claire-go.service`, port 8080, binary built to `/tmp`). Not traced into `claire_runtime.py`'s call graph in this session's work; not confirmed whether `handle_user_message` calls it at all versus it being a separate, parallel service. |
| **Q Insight** | **FULLY IMPLEMENTED, in live path** | `q_insight_packet()` called at `claire_runtime.py:418`, event `q_insight.result` logged to Truth Spine, result gates `clarification_blocks` logic that can short-circuit the turn. Real control-flow impact, not decorative. |
| **GYRO** | **FULLY IMPLEMENTED, in live path, but reordered** | `GyroOrientationLayer.orient()` called at `claire_runtime.py:276`, real stability gate that can short-circuit the turn (`:301`). Runs *before* Recognition Rail/Q Insight, not after, contrary to the stated intended architecture. |
| **BARE** | **DEMO-ONLY / UI-ONLY** | Zero references anywhere in `claire_runtime.py` or `claire/runtime/gyro.py`. Every `bare_role`/`BARE` occurrence found is inside demo-report-building or marketing-copy functions in `claire_gui.py` (`build_demo_report_markdown`, `ooda_demo_artifacts`, static HTML labels). |
| **FARE** | **DEMO-ONLY / UI-ONLY** | Same evidence and conclusion as BARE. |
| **Recognition Rail** | **FULLY IMPLEMENTED, in live path, but reordered** | `recognition_packet_from_are()` called at `claire_runtime.py:396`, event `recognition_rail.result` logged. Runs after Gyro and after ARE recall, not before Veritas parsing as the intended order states (there is no Veritas parsing stage to be before). |
| **3CRP** | **PARTIALLY IMPLEMENTED** | Present as multiple discrete gate calls (`runtime_3crp.admit_input`, `.authorize_recall`, `.authorize_temporal_operation`, `.authorize_model`, `.authorize_memory_write`, `.authorize_output`) throughout `handle_user_message`, each logged to Truth Spine and each capable of denial. Real, not decorative. But it is not a single "ingress then later routing" two-pass structure as described in the intended architecture — it's ~6 separate authorization checks interleaved with other stages. |
| **Ledger / Truth Spine** | **FULLY IMPLEMENTED, in live path** | Two implementations exist (`claire_runtime_truth.py` live; `claire_are/truth_spine.py` unused). The live one hash-chains and HMAC-signs every event (~22 per turn) and every field the brief worried about (lane, sequence, timestamp) is inside the hashed envelope in both implementations — no evidence found of a payload-only-hash vulnerability in current code. Contains the flock-with-no-timeout defect (Phase 9 below). |
| **Sentinel** | **CONNECTED BUT LIMITED** | `RuntimeSentinel.authorize_memory_write()` called once, late, at `claire_runtime.py:648` — specifically for memory-write authorization only, not as a general pre-execution safety/contradiction gate as its description in the brief implies. |
| **Veritas** | **CONNECTED BUT LIMITED (trading lane); separate real service (Legal)** | Trading-lane status is local-file/env checks only, conditionally called (`_subsystem_status_for_lane`, `claire_runtime.py:1173`), not a general parsing/provenance stage. Veritas Legal is a substantial, real, separately-deployed FastAPI service (30+ routes, port 8020) — functional but architecturally disconnected from `ClaireRuntime`'s governance pipeline (it's its own app, not a stage inside `handle_user_message`). |
| **Diode / WriteBarrier** | **PARTIALLY IMPLEMENTED** | `DiodeProtocol.redact()`/`.contains_secret()` called repeatedly for PII/secret redaction. No distinct pre-model-execution "what may pass forward" enforcement gate found separate from this redaction role. |
| **Provenance** | **PARTIALLY IMPLEMENTED** | Truth Spine events carry hashes and parent-event chains; `are_record_refs`/`evidence_refs` fields exist and are populated. Not independently verified whether provenance survives into the Veritas Legal service's separate document pipeline. |
| **Policy enforcement / tool authority / approval gates** | **PARTIALLY IMPLEMENTED** | `AuthorityCapsule`/`HandshakeBroker` gate tool and memory-scope access per request; not evaluated against a full policy-authoring UI or externalized policy config (none found). |
| **Model routing** | **PARTIALLY IMPLEMENTED / MOSTLY HARDCODED** | `nemotron_adapter.call_nemotron` chooses remote NVIDIA vs. local llama.cpp bridge based on whether `NVIDIA_API_KEY` is set — a single environment-variable branch, not a policy-driven router across multiple models/providers. |
| **Memory governance** | **FULLY IMPLEMENTED, in live path** | `memory_eligibility.py`, `EchoShield`, `Sentinel`, and 3CRP all gate memory writes in sequence before `_commit_memory` runs (`claire_runtime.py:648-703`). |
| **Trace replay** | **PARTIALLY IMPLEMENTED** | `/trace/{trace_id}` reconstructs a record from SQLite or JSONL fallback (`trace_logger.py`), but this pass did not verify whether replaying reconstructs the *decision path* (all the intermediate gate events) or only the final summary record — flagged as an open question. |
| **Lycanthrope** (overwatch) | **STUB / PRESENT BUT BYPASSED** | `claire_core/adapters/lycanthrope.py` — a static `RuntimeMode`/`ModePermissions` matrix plus a `transition()` method gated by an externally supplied Sentinel decision. No threads, no async loop, no tamper/duress detection logic of any kind. **Zero references anywhere in `claire_runtime.py`** — never instantiated, never called. Its only other appearance in the live app is an unrelated string literal inside a content-filter keyword list (`claire_gui.py:7450`). It is neither the blocking-per-turn anti-pattern the brief worried about, nor the background/async overwatch it's meant to be — it is simply not wired to run at all. |

## 11. Model and Tool Integrations (Phase 9)

| Provider | Model | Adapter | Endpoint | Timeout | Notes |
|---|---|---|---|---|---|
| NVIDIA NIM (remote) | `nvidia/nemotron-3-ultra-550b-a55b` (default, overridable) | `nemotron_adapter.py:42-71` | `https://integrate.api.nvidia.com/v1/chat/completions` (overridable via `NVIDIA_NIM_BASE_URL`) | **Explicit, 60s default** (`model_config.get("timeout", 60)`) | Used only if `NVIDIA_API_KEY` is set. Auth via Bearer token env var. |
| Local llama.cpp bridge | Whatever's loaded on the target `llama-server` | `nemotron_adapter.py:74-100` | `http://127.0.0.1:8080/completion` (or `LLM_BASE_URL`/`CLAIRE_LOCAL_LLM_URL`) — **note: default base URL is port 8080, the Go backend, not 8091/8092 where the actual llama.cpp model servers listen**, unless overridden by env | **Explicit, 60s default per attempt, 2 attempts** | Used as fallback when no NVIDIA key. **This default-port mismatch (8080 vs 8091/8092) is worth independently confirming** — if `CLAIRE_LOCAL_LLM_URL`/`LLM_BASE_URL` isn't set in the live `.env`, this fallback would be hitting the wrong service. Not confirmed this pass whether the env var is actually set correctly in production `.env` (not read, per instructions — only path/name confirmed to exist). |
| Local llama.cpp, direct | Qwen3.5-9B / Qwen3-14B (Q4_K_M) | `llama-server` processes | `127.0.0.1:8091`, `127.0.0.1:8092` | N/A (not an app-level call) | Two real model servers running, CPU inference (`-ngl 0`), 8192 context. Not reachable from outside the VM (`127.0.0.1` bind). |
| Gemini | Unspecified | referenced via `is_gemini_available()`/`LAST_GEMINI_ERROR` | Not traced this pass | Not confirmed | "GEMINI READY" in the status payload reflects `is_gemini_available()` truthiness, not necessarily a live successful call — see Phase 7. |
| CourtListener | N/A (legal research API) | `claire_courtlistener.py` | External REST API | **Explicit, 30s and 20s** | Real HTTP client, proper timeouts. |

**"Machine Called: NO" in runtime terms:** as established in Phase 5, this is almost always a hardcoded UI constant, not a signal derived from whether `call_nemotron` (or any tool) actually executed. **"Gemini READY" in runtime terms:** reflects a boolean availability check, not confirmed this pass to be a live round-trip probe — treat as unverified until `is_gemini_available()`'s implementation is read.

**Connected tools identified:** Drive (`/drive/status`, `/drive/research` — the one place `machineCalled` is set dynamically), CourtListener (real, timed API client), Veritas Legal's own EDGAR/CourtListener/OCR/ingest tool surface (separate service, port 8020, not further audited this pass), local document upload/ingest (`/upload`, `/upload-folder` → `claire-ingest.service`), voice (browser SpeechRecognition, client-side only — no server-side voice processing found in the traced path). No evidence found this pass of Gmail, GitHub, browser automation, or Azure-operations tool integrations inside `claire_gui.py`/`claire_runtime.py` specifically — if these exist, they're elsewhere in the repo and were not located in this pass.

## 12. Storage, Memory, Provenance, and Trace (Phase 10)

Confirmed storage technologies actually used by the core governed path (as distinct from the unused Postgres/Redis/Qdrant/Neo4j/MinIO containers noted in Phase 1):

| Data | Technology | Path |
|---|---|---|
| Runtime Truth Spine (hash-chained event log) | Flat JSONL, `fcntl`-locked | `data/runtime_truth_spine.jsonl` (relative to `claire-gui.service`'s `WorkingDirectory=/home/LuciusPrime/claire`), degraded fallback `data/runtime_truth_spine_degraded.jsonl` |
| ARE chronological memory | Flat JSONL | Path resolved by `original_are_bridge.py`, defaulting toward `/home/LuciusPrime/original_are.pyiginal_are.py/are_data/are_mem.jsonl` unless `CLAIRE_ORIGINAL_ARE_MEM_PATH` overrides it |
| Runtime traces | SQLite + JSONL mirror | `claire_state/claire_runtime_traces.db`, `data/claire_runtime_traces.jsonl` |
| Public demo traces | SQLite | `data/public_demo.sqlite` (separate from the above) |
| `AREMemoryStore` (SQLite, alternate memory implementation) | SQLite | `claire_state/claire_memory.db` — **defined but not instantiated** in the live `ClaireRuntime()` default construction (confirmed: `memory_store=None` in production) |

**Restart persistence:** JSONL and SQLite stores are on local disk, so they survive process restarts. **Tenant isolation:** no evidence found of per-tenant namespacing anywhere in these paths — all data appears to write to single, shared files/DBs. **Concurrency risk:** the Truth Spine's `fcntl.flock` (Phase 9) is the main serialization point and, being unbounded, is also the main concurrency *risk* — under contention it doesn't degrade gracefully, it hangs. **Encryption at rest:** not evaluated this pass (would require checking filesystem/disk-level config, out of scope for a code/process audit). **Trace reconstruction:** `/trace/{trace_id}` can return a full record including a `runtime_truth_event_ids` map (all ~14 named stage event IDs for that turn, per the trace_record structure at `claire_runtime.py:817-886`) — so in principle a trace *can* reconstruct the full decision path, provided the corresponding Truth Spine events are also fetched by those IDs. Whether the current `/trace/{trace_id}` handler actually resolves and returns those nested events, or just the flat summary, was **not verified this pass** — flagged as an open question.

## 13. Security Findings (Phase 11)

Findings from safe, read-only inspection only — nothing was exploited.

| Finding | Severity | Evidence |
|---|---|---|
| Unbounded blocking lock in the hot path (`fcntl.flock`, no timeout) reachable on every governed request | **HIGH** (availability) | `claire_runtime_truth.py:130`, hit ~22×/turn — see this session's earlier detailed trace. A stuck or contended writer can hang every subsequent request indefinitely. |
| `/status` shell-executes `ss -tulnp | grep <port>` via `subprocess.check_output(..., shell=True)` on every poll (every 5s per connected client) | **LOW** | `claire_gui.py:16728` etc. Arguments are hardcoded, not user-controlled, so not directly injectable — but `shell=True` with string interpolation is a pattern worth tightening, and running a subshell 4× per status poll at high client counts is unnecessary load. |
| `llm` status check watches the wrong port (8080, Go backend) instead of the real model servers (8091/8092) | **MEDIUM** (integrity of a trust signal) | Confirmed by direct comparison of `claire_gui.py:16733-16737` against the actual `llama-server` listening ports. A false "ONLINE" is a worse failure mode than a false "OFFLINE" for a status page investors/customers might see. |
| Workflow-debug HUD (`Control Layer`, `Machine Called`) is mostly hardcoded UI copy, not derived from server truth | **MEDIUM** (integrity of a trust signal) | 27/28 `machineCalled` occurrences are literal `"NO"` strings, confirmed by exhaustive grep. If this HUD is ever shown to a customer/investor as evidence of governance, it is currently not reliable evidence. |
| Several backend routes are defined in code but have no nginx exposure and 404 publicly (`/truth-spine/status`, `/are-spectacle`, `/scholar`, `/privacy`, `/terms`, `/support`, `/office/*`, `/report/{id}`) | **LOW–MEDIUM** | Verified live for three of these; not a security hole per se (fails closed), but a functional gap and a sign of drift between backend route additions and nginx config maintenance. |
| `ingest.log` is owned by `root` while the app runs as `LuciusPrime` | **LOW, needs follow-up** | `ls -la` shows `root:root` ownership on a log file in a directory otherwise owned by `LuciusPrime` — worth confirming what process writes it and whether it implies something in the ingest path runs with elevated privileges unexpectedly. Not further investigated this pass. |
| `claire-gui.service` (port 8000, the process serving the public domain) has been running since 2026-07-17 00:16 UTC and has not reloaded code committed after that time | **LOW–MEDIUM** (operational, not exploitable) | Confirmed via `systemctl show` + `git log`. Any bug fix or security patch committed to `claire_gui.py` in the last several days is **not live** until the service is restarted. This is a real gap between "what's in the repo" and "what's actually serving traffic" that should be checked before relying on any code-only finding in this report as a description of current live behavior. |
| No committed-secret pattern matches found in a coarse scan (`AKIA...`, `BEGIN PRIVATE KEY`, `sk-...`) across tracked files | **INFORMATIONAL** | Not exhaustive — only a fast pattern grep, not a full secret-scanning tool run. |
| `/machine/*` and `/action` are nginx-blocked with 403 before reaching the backend | **INFORMATIONAL / looks intentional** | Reads as a deliberate boundary preventing public traffic from reaching whatever those routes do server-side; worth having the operator confirm this is intended and not accidentally blocking something that should be reachable internally. |
| No API-key auth, rate limiting, or per-tenant request-size limits observed anywhere in the traced `/reply` path | **HIGH** (for the SaaS-gateway objective specifically, not for the current single-tenant demo) | Confirmed absent in everything read this session; this is expected for a single-operator demo site and not itself a "vulnerability" today, but is a blocking gap for Phase 12/14 commercialization. |

No exposed credentials, no arbitrary file upload paths, no path traversal, no command-execution routes, and no cross-tenant data-mixing were found — but this reflects the specific files read this session, not an exhaustive application-security review of all ~17,000 lines of `claire_gui.py` or the separate Veritas Legal (port 8020) codebase. Treat the absence of findings there as "not found in this pass," not "confirmed absent."

## 14. SaaS Gateway Readiness Matrix (Phase 12)

| Capability | Status |
|---|---|
| API authentication | **MISSING** — no API-key or bearer-token gate found on `/reply` or any other route |
| Customer accounts | **MISSING** |
| Tenant isolation | **MISSING** — all storage paths are single, shared files/DBs (Phase 10) |
| License keys / service keys | **MISSING** |
| Role-based access | **PARTIAL** — `AuthorityCapsule`/`HandshakeBroker` gate scopes and tools per-request, but there's no external identity/account system driving it; roles look to be resolved from request metadata, not a customer directory |
| Policy profiles | **PARTIAL** — gates exist (3CRP, Sentinel) but no externalized, editable policy configuration was found; policy logic reads as code, not data |
| Model connectors | **PARTIAL / REQUIRES REFACTOR** — two providers wired (NVIDIA NIM, local llama.cpp) via one hardcoded env-var branch, not a pluggable connector interface |
| Tool connectors | **PARTIAL** — Drive, CourtListener exist; no generalized tool-connector abstraction found |
| Usage metering | **MISSING** |
| Billing hooks | **MISSING** |
| Quotas | **MISSING** |
| Audit logs | **EXISTS** — Truth Spine + trace_logger, real and hash-chained |
| Trace replay | **PARTIAL** — records exist and are fetchable; full decision-path reconstruction not confirmed |
| Customer dashboard | **MISSING** (the public demo GUI is not a customer/tenant dashboard) |
| Monitoring | **PARTIAL** — `/status` exists but mixes real and shallow checks (Phase 7); no external monitoring/alerting integration found |
| Rate limiting | **MISSING** |
| Webhook support | **MISSING** (not found in this pass) |
| Backups | **UNKNOWN** — backup scripts exist by name at repo root (Phase 1) but were not individually read this pass to confirm what they actually back up or their schedule |
| Disaster recovery | **UNKNOWN** |
| Deployment automation | **PARTIAL** — 10 bootstrap/pulse shell scripts exist, suggesting iterative manual deployment rather than a single reproducible pipeline (e.g., no Dockerfile/Compose found for the core `claire_gui.py` app itself — only `claire_vde` and the data services are containerized) |
| Documentation | **UNKNOWN** — not assessed this pass |
| Tests | **PARTIAL** — a `tests/` directory and scattered `test_*.py` files exist repo-wide; coverage of `claire_runtime.py`'s actual live pipeline was not assessed this pass |
| Versioning | **MISSING** — no versioned API path (e.g. `/v1/...`) found on any governed route |

## 15. Recommended Target Architecture (Phase 13)

Preserve, don't rewrite: `claire_runtime.py` + `claire_runtime_truth.py` are the real asset and should become **CLAIRE Core**, extracted from `claire_gui.py` as an importable package with no FastAPI/HTML coupling. Everything else should be built *around* that extraction, not instead of it.

```
                         ┌─────────────────────────┐
                         │   CLAIRE Gateway API      │  new: versioned (/v1),
                         │  (thin FastAPI service)   │  API-key auth, tenant
                         └────────────┬──────────────┘  context injection
                                      │  calls
                         ┌────────────▼──────────────┐
                         │       CLAIRE Core          │  = claire_runtime.py +
                         │ (ClaireRuntime, extracted, │    claire_runtime_truth.py,
                         │  no web framework coupling)│    unchanged logic, fix the
                         └───┬───────┬───────┬────────┘    flock timeout here
                             │       │       │
                 ┌───────────▼─┐ ┌───▼────┐ ┌▼──────────────┐
                 │Model adapters│ │ Policy  │ │ Memory/        │  = nemotron_adapter,
                 │(pluggable)   │ │ engine  │ │ Provenance/    │    pick ONE ARE lineage
                 │              │ │(3CRP/   │ │ Audit & Replay │    (recommend: keep
                 │              │ │Sentinel)│ │                │    original_are_bridge +
                 └──────────────┘ └─────────┘ └────────────────┘    faiss_are_index,
                                                                     retire the other 3)
                         ┌─────────────────────────┐
                         │   CLAIRE Demo UI          │  = today's claire_gui.py
                         │ (public marketing/demo)   │    HTML/JS, kept, but its
                         └────────────┬──────────────┘    /reply calls go through
                                      │                    the new Gateway API like
                                      ▼                    any other customer would
                         (clairesystems.ai, unchanged)

        Separate, not touched by the above: Customer identity + Licensing
        (new), Tool adapters (Drive/CourtListener/EDGAR, generalize the
        pattern already used by claire_courtlistener.py), Deployment config
        (consolidate the 10 bootstrap scripts into one, containerize CLAIRE
        Core + Gateway the way claire_vde already is).
```

**This VM's role going forward:** keep it as the **demo/staging host** for now — it is where the real, working governance engine currently lives and where `clairesystems.ai` already resolves with valid TLS, so it's the fastest path to Phase 16's demo. It should **not** remain the long-term production host for a multi-tenant commercial product, because tenant isolation, secrets management, and the mixed single-process deployment model (HTML demo + governance engine + 47 routes in one FastAPI app) don't belong in a customer-facing production tier. Recommend: containerize CLAIRE Core + Gateway API as a first milestone, deploy that as a separate service (can still live on this VM initially), and only retire this VM once the containerized path has run in parallel long enough to trust it — do not migrate and decommission in the same step.

## 16. First Commercial Demo Specification (Phase 14)

**Scenario:** "Same model, same document, same question." Upload one document via the existing `/upload` flow. Ask a question whose unsupported/ungoverned answer is easy to show as wrong or unauthorized (e.g., a request that should trigger a Sentinel/authority denial, or a request where an ungoverned model will confidently fabricate an answer with no source).

- **Run A (ungoverned):** curl the local llama.cpp server directly (`127.0.0.1:8091` or `:8092`) with the same prompt, bypassing `claire_runtime.py` entirely. Show the raw, unsourced, unauthorized answer.
- **Run B (governed):** send the identical prompt through non-demo `/reply`. Show: the Sentinel/authority decision (or a successful, memory-grounded answer with citations), the Truth Spine `trace_id`, and a live `/trace/{trace_id}` fetch proving the decision is recorded and replayable.

**Existing components reused:** `claire_runtime.py` (no changes needed), `/reply` (no changes needed), `/trace/{trace_id}` (no changes needed), `/upload` (no changes needed), the local llama-server for Run A (already running).
**New code required:** a small comparison UI (or even a two-pane terminal/script demo) placing Run A and Run B side by side — this is presentation work, not governance engineering. Optionally: fix `machineCalled`/`controlLayer` to reflect real response data so the HUD doesn't undercut the demo by showing "NO" during a run that did call the model.
**API endpoints:** none new required.
**Trace output:** the existing `/trace/{trace_id}` JSON, possibly formatted for readability.
**Success metric:** an observer can see, without narration, that Run A produced an unchecked answer and Run B produced either a blocked/escalated response or a cited, replayable one.
**Build difficulty:** Low. **Estimated engineering hours:** 1-2 days for a clean, presentable version (most of the time is UI polish and picking a compelling prompt/document, not backend work).
**Risks:** the `flock` timeout issue (Phase 9) could cause Run B to hang mid-demo if triggered; fix or work around that first (see Phase 17, Priority 0).

## 17. Prioritized Repair and Productization Plan (Phase 15)

**Phase 0 — Preserve** *(do before touching anything else)*
- Git: current state is clean on tracked runtime files; the 70 untracked docs/scratch files should be committed or explicitly gitignored so `git status` stops being noisy — no risk either way, but do it before any repair work so diffs stay legible.
- Config capture: copy `/etc/nginx/sites-enabled/claire`, all `/etc/systemd/system/claire-*.service` unit files, and `docker ps` output into the repo's ops-documentation (they currently exist only on the live host).
- VM snapshot: recommend an Azure disk snapshot before any of Phase 1 below, given `Restart=always` means a bad code push auto-restarts into the same bad state.

**Phase 1 — Repair**
| Task | Priority | Files | Difficulty | Risk |
|---|---|---|---|---|
| Add a timeout (or replace with a lockless/queued design) around `fcntl.flock` | **P0** | `claire_runtime_truth.py:128-171` | Medium | Low — additive change, doesn't alter the hash chain format |
| Point the `llm` status check at 8091/8092 instead of 8080, or rename what 8080's check actually reports | P1 | `claire_gui.py:16733-16737` | Low | Low |
| Add nginx `location` blocks for the confirmed-missing routes (`/truth-spine/status`, `/are-spectacle`, `/scholar`, `/privacy`, `/terms`, `/support`, `/office/*`, `/report/{id}`) or deliberately decide they should stay unpublished | P1 | `/etc/nginx/sites-enabled/claire` | Low | Low, but is infra, not repo — coordinate with whoever manages this VM |
| Restart `claire-gui.service` (or set up a redeploy hook) so the 2.5-day code/process drift stops compounding | P1 | ops only | Low | **Medium** — this is a live public service; time it deliberately |
| Wire real `machineCalled`/`controlLayer` values from server responses instead of hardcoded literals, at minimum in the paths meant to demonstrate governance | P1 | `claire_gui.py` (28 call sites) | Medium | Low |
| This can all be done **without changing the pipeline architecture** — every item above is a bounded, local fix. |

**Phase 2 — Unify**
Make the control layer mandatory (remove/relabel the demo-vs-real ambiguity so a viewer can always tell which path produced a given response); standardize the request/response schema between demo and non-demo `/reply`; ensure every response — demo included — carries a real `trace_id`.

**Phase 3 — Expose**
Extract `ClaireRuntime` from `claire_gui.py` into an importable package (no FastAPI coupling); stand up a thin, versioned Gateway API (`/v1/...`) in front of it with API-key auth; define one model-adapter interface instead of the current single env-var branch.

**Phase 4 — Demonstrate**
Build the Phase 16 demo above; put it behind a clean UI separate from the current 17,000-line demo app.

**Phase 5 — Commercialize**
Tenant isolation (namespace the JSONL/SQLite paths per-tenant, or move to the already-running-but-unused Postgres), licensing, usage metering, billing hooks, private/Dockerized deployment (containerize CLAIRE Core the way `claire_vde` already is), documentation, pilot onboarding.

## 18. 30-Day Productization Plan

Week 1: Phase 0 (Preserve) + Phase 1 (Repair) items above, all P0/P1. Week 2: extract CLAIRE Core as a standalone package; write the model-adapter interface; add API-key auth to a new thin Gateway. Week 3: build and rehearse the Phase 16 demo end-to-end multiple times under realistic conditions (including a deliberate high-load test against the flock fix). Week 4: containerize CLAIRE Core + Gateway; draft tenant-isolation design (even if not fully implemented) so the first pilot customer's data path is answerable in one sentence.

## 19. What Must Not Be Rewritten

- `claire_runtime.py`'s `handle_user_message()` sequencing logic and its Truth Spine event schema — it works, is already hash-chained and signed, and rewriting it risks losing audit continuity for existing sealed turns.
- `claire_runtime_truth.py`'s hashing scheme itself (the envelope structure, HMAC signing, chain verification) — confirmed sound against the specific vulnerability pattern the operator asked about (payload-only hashing). Only the `flock` call needs to change, not the surrounding cryptographic design.
- `nemotron_adapter.py`'s existing timeout handling — it's correctly bounded already; extend it (pluggable connectors) rather than replace it.
- The nginx TLS/cert setup — it's live, valid, and working; changes here should be additive (`location` blocks) not structural.

## 20. Open Questions and Missing Evidence

- Whether `build_governed_demo_payload()` internally calls `ClaireRuntime` or synthesizes its response — not read this pass.
- Whether `/trace/{trace_id}` returns the full nested decision path (all stage events) or only the flat summary record — not confirmed.
- What `is_gemini_available()` actually checks (key presence vs. live probe) — not read this pass.
- Whether `CLAIRE_LOCAL_LLM_URL`/`LLM_BASE_URL` are set correctly in the live `.env` (not read, per instructions not to expose secrets — only confirmed the files exist).
- What the 5 Postgres/Redis/Qdrant/Neo4j/MinIO Docker containers are actually for, if not the core governed path — plausibly `claire_vde`, not confirmed.
- Contents and correctness of the 10 bootstrap/deployment shell scripts and the backup scripts referenced in the brief — not individually read this pass.
- Full security review of the separate Veritas Legal service (port 8020, 30+ routes) and `claire_gui.py`'s remaining ~16,000 unread lines — this audit focused on the routes and functions directly relevant to the reported symptoms, not an exhaustive line-by-line review of the entire codebase.
- Whether anything outside this VM (CDN, load balancer, DNS-level routing) also touches `clairesystems.ai` traffic — not checked, this audit was VM-local.

## 21. Exact Commands Used During Investigation

All commands were read-only (process/service/network inspection, `git log`/`diff`/`grep`/`blame`, `curl` against already-running local services, `ls`/`du`/`cat` on config and log files). No `docker` state-changing command, no `systemctl start/stop/restart`, no file writes other than this report, and no destructive git operations were run. Representative commands: `hostnamectl`, `ss -tlnp`, `systemctl status/show/cat/list-units`, `docker ps` / `docker inspect`, `git log/diff/blame/status`, `cat /etc/nginx/sites-enabled/claire`, `nginx -t`, `journalctl -u nginx`, `curl -X POST https://127.0.0.1/veritas-legal/run -H "Host: clairesystems.ai"`, `curl http://127.0.0.1:8000/...` (multiple routes), `grep`/`sed` across `claire_gui.py`, `claire_runtime.py`, `claire_runtime_truth.py`, and related modules, `sudo -n certbot certificates` (read-only, non-interactive).

## 22. Appendix — Key File/Function/Line References

- `claire_gui.py:171` — `CLAIRE_GOVERNED_RUNTIME = ClaireRuntime()` instantiation.
- `claire_gui.py:14955` / `:12805` — `/reply` route → `build_reply()`.
- `claire_gui.py:5874-5881` — idle-state workflow-debug object (`route: "idle"`).
- `claire_gui.py:6802-6829` — `checkStatus()`, source of "[STATUS ERROR] Failed to fetch".
- `claire_gui.py:16721-16804` — `/status` handler, mixed real/shallow checks.
- `claire_gui.py:15823` — `/veritas-legal/run` route definition.
- `claire_runtime.py:111-890` — `ClaireRuntime.handle_user_message()`, the full governed pipeline.
- `claire_runtime_truth.py:112-171` — `RuntimeTruthSpine.append`/`_append_safe_event`, including the unbounded `fcntl.flock` at line 130.
- `claire_core/adapters/lycanthrope.py:47-84` — `Lycanthrope` class, confirmed unwired.
- `/etc/nginx/sites-enabled/claire` — live nginx config; `claire.before_veritas_legal_20260719_090921` — pre-fix backup.
- `/etc/systemd/system/claire-gui.service` — unit definition for the port-8000 process.
