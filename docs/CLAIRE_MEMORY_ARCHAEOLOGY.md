# CLAIRE Memory Architecture Archaeology

Audit date: 2026-07-12 UTC

Scope: live CLAIRE services on the Azure BLUE host, local source trees, active data stores, and memory/index implementations. This report is observational only. No services were stopped, restarted, migrated, or modified.

Secret handling: environment variables and token-bearing configuration were inspected by name only. Secret values are intentionally redacted and are not reproduced here.

## 1. Executive Verdict

CLAIRE has several real memory paths, but they are not one unified authoritative memory architecture.

The live system currently has three important memory authorities:

- `claire-are.service`: JSONL vault at `/home/LuciusPrime/claire/data/memory_vault.jsonl`, used by the ingest bridge and document/upload memory.
- `ClaireRuntime` default memory path: Original ARE JSONL at `/home/LuciusPrime/original_are.pyiginal_are.py/are_data/are_mem.jsonl`, used by the governed chat runtime when `ClaireRuntime()` is constructed with default settings.
- `are-spectacle.service`: separate SQLite store at `/home/LuciusPrime/are-spectacle-v2/data/spectacle.db`, used by ARE Spectacle v2 but not the primary public GUI response path.

The strongest live production-style path is:

`GUI upload -> claire-ingest.service -> sentinel_spine.jsonl -> claire-are.service -> memory_vault.jsonl -> in-memory token/exact indexes`

The strongest governed chat path is:

`/ask -> ClaireRuntime.handle_user_message -> route/orient -> Original ARE recall -> provider call -> Original ARE commit -> runtime trace`

The live architecture preserves useful memory and trace data across restarts, but it does not yet provide a single globally ordered Truth Spine for every memory write. Some stores are append-oriented, some are SQLite append tables, and some are derived/session/demo stores. The current root disk is also nearly full, so the system cannot safely support a growing Venture Intelligence evidence archive without a durable storage tier.

Final conclusion is at the end of this report.

## 2. Live Service Map

### are-spectacle.service

| Field | Value |
|---|---|
| Status | Active/running |
| Unit path | `/etc/systemd/system/are-spectacle.service` |
| User | `LuciusPrime` |
| Working directory | `/home/LuciusPrime/are-spectacle-v2` |
| ExecStart | `/home/LuciusPrime/are-spectacle-v2/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010` |
| Active PID | `1323350` |
| Port | `127.0.0.1:8010` |
| Source directory | `/home/LuciusPrime/are-spectacle-v2` |
| Data directory | `/home/LuciusPrime/are-spectacle-v2/data` |
| Primary data store | `/home/LuciusPrime/are-spectacle-v2/data/spectacle.db` |
| Log location | `/home/LuciusPrime/are-spectacle-v2/spectacle.log` |
| Restart policy | `Restart=always`, `RestartSec=5` |

Health result:

```json
{"status":"ok","product":"ARE Spectacle v2","records":55}
```

### claire-are.service

| Field | Value |
|---|---|
| Status | Active/running |
| Unit path | `/etc/systemd/system/claire-are.service` |
| User | `LuciusPrime` |
| Working directory | `/home/LuciusPrime/claire` |
| ExecStart | `/home/LuciusPrime/claire/venv/bin/uvicorn ARE_SERVER:app --host 127.0.0.1 --port 8002` |
| Active PID | `1323351` |
| Port | `127.0.0.1:8002` |
| Source file | `/home/LuciusPrime/claire/ARE_SERVER.py` |
| Data directory | `/home/LuciusPrime/claire/data` |
| Primary data store | `/home/LuciusPrime/claire/data/memory_vault.jsonl` |
| Log location | `/home/LuciusPrime/claire/are.log` |
| Restart policy | `Restart=always` |

Health result:

```json
{"status":"online","mode":"ARE_FAST_INDEXED","vault_records":8463,"vault_path":"/home/LuciusPrime/claire/data/memory_vault.jsonl"}
```

### claire-gui.service

| Field | Value |
|---|---|
| Status | Active/running |
| Unit path | `/etc/systemd/system/claire-gui.service` |
| User | `LuciusPrime` |
| Working directory | `/home/LuciusPrime/claire` |
| ExecStart | `/home/LuciusPrime/claire/venv/bin/uvicorn claire_gui:app --host 0.0.0.0 --port 8000` |
| Active PID | `1323352` |
| Port | `0.0.0.0:8000` |
| Source file | `/home/LuciusPrime/claire/claire_gui.py` |
| Data directory | `/home/LuciusPrime/claire/data` |
| Trace paths | `/home/LuciusPrime/claire/data/traces.jsonl`, `/home/LuciusPrime/claire/data/claire_runtime_traces.jsonl`, `/home/LuciusPrime/claire/claire_state/claire_runtime_traces.db` |
| Log location | `/home/LuciusPrime/claire/gui.log` |
| Environment names | `CLAIRE_ADMIN_ACTION_TOKEN`, `CLAIRE_NEMO_GUARDRAILS`, and runtime path/provider variables; values redacted |
| Restart policy | `Restart=always` |

Health result:

```json
{"status":"ok","service":"Claire Public Demo"}
```

### claire-ingest.service

| Field | Value |
|---|---|
| Status | Active/running |
| Unit path | `/etc/systemd/system/claire-ingest.service` |
| User | `LuciusPrime` |
| Working directory | `/home/LuciusPrime/claire` |
| ExecStart | `/home/LuciusPrime/claire/venv/bin/uvicorn claire_ingest_bridge:app --host 127.0.0.1 --port 8081` |
| Active PID | `1323353` |
| Port | `127.0.0.1:8081` |
| Source file | `/home/LuciusPrime/claire/claire_ingest_bridge.py` |
| Data directory | `/home/LuciusPrime/claire/silo_data` |
| Primary data store | `/home/LuciusPrime/claire/silo_data/sentinel_spine.jsonl` |
| Forward target | `http://127.0.0.1:8002/ingest` |
| Log location | `/home/LuciusPrime/claire/ingest.log` |
| Restart policy | `Restart=always` |

Health result:

```json
{"ok":true,"service":"claire-ingest","port":8081,"lane":"parser_to_sentinel_to_are","are_ingest_url":"http://127.0.0.1:8002/ingest","external_ingest":false}
```

### claire-go.service

| Field | Value |
|---|---|
| Systemd status | Activating / auto-restart, result `exit-code` at inspection time |
| Unit path | `/etc/systemd/system/claire-go.service` |
| Working directory | `/home/LuciusPrime/claire` |
| ExecStart | `/usr/bin/go run /home/LuciusPrime/claire/main.go` |
| Intended port | `127.0.0.1:8080` |
| Observed live process | A separate `go run` / compiled child was listening on `127.0.0.1:8080` |
| Log location | `/home/LuciusPrime/claire/go.log` |
| Restart policy | `Restart=always` |

Observed root endpoint returned a CLAIRE NODE HTML page, but visible page text included a provider-unavailable state. This service needs separate provider validation before treating it as a working model gateway.

### cloudflared.service

| Field | Value |
|---|---|
| Status | Active/running |
| Unit path | `/etc/systemd/system/cloudflared.service` |
| ExecStart | `cloudflared --no-autoupdate tunnel --url http://127.0.0.1:8000 run --token-file /etc/cloudflared/tunnel.token` |
| Active PID | `3243428` |
| Route | Public tunnel to `claire-gui.service` on `127.0.0.1:8000` |
| Secret material | Token file exists; value not inspected or reproduced |

### Veritas Legal service

| Field | Value |
|---|---|
| Status | Running process, not identified as a systemd service in the inspected CLAIRE service list |
| Active PID | `1971126` |
| Working directory | `/home/LuciusPrime/claire_repos/claire-veritas-legal` |
| Command | `/home/LuciusPrime/claire/venv/bin/python -m uvicorn web.app:app --host 0.0.0.0 --port 8020` |
| Port | `0.0.0.0:8020` |
| Environment names | Includes `ARE_BASE_URL`, `CLAIRE_DATA_ROOT`, `COURTLISTENER_API_KEY`, `GEMINI_API_KEY`; values redacted |

### Temporary test service observed

| Field | Value |
|---|---|
| Port | `0.0.0.0:8011` |
| PID | `3593283` |
| Command | `uvicorn claire_gui:app --host 0.0.0.0 --port 8011` |
| Classification | Temporary/test process from prior mobile UI validation, not Azure BLUE production routing |

## 3. Actual Memory Write Path

### Normal governed chat path

The public GUI `/ask` flow is implemented in `/home/LuciusPrime/claire/claire_gui.py`.

Observed code path:

1. `claire_gui.py` receives user input.
2. `build_reply(q)` calls `CLAIRE_GOVERNED_RUNTIME.handle_user_message(...)`.
3. `ClaireRuntime.handle_user_message` in `/home/LuciusPrime/claire/claire_runtime.py`:
   - creates a trace id;
   - normalizes and diode-filters the request;
   - classifies lane via C3RP;
   - checks authority and posture;
   - runs `_recall_memory(...)`;
   - builds provider context;
   - calls the configured provider through the `provider_generate` callback;
   - validates and loopback-checks output;
   - commits memory through `_commit_memory(...)`;
   - writes trace through `TraceLogger`.
4. With default construction, `ClaireRuntime(use_original_are=True)` uses Original ARE through `/home/LuciusPrime/claire/original_are_bridge.py`.
5. The durable chat memory write target is `/home/LuciusPrime/original_are.pyiginal_are.py/are_data/are_mem.jsonl`.

Answers to required questions:

| Question | Finding |
|---|---|
| Does ARE consult occur before every model call? | In the governed `ClaireRuntime.handle_user_message` path, recall occurs before provider generation. Legacy/direct paths should be treated separately and not assumed governed without per-route validation. |
| Is the user request written before recall? | In the governed runtime path, the observed sequence is route/orient -> recall -> provider -> memory commit. The user request is not durably committed to Original ARE before recall in that path. |
| Is the model response written afterward? | Yes, if the memory admission policy allows it, `_commit_memory(...)` writes the post-turn record after provider generation. |
| Are rejected writes recorded? | Not consistently across live stores. SQLite `AREMemoryStore` has `memory_audit_log`, but default runtime uses Original ARE. ARE Spectacle WriteBarrier rejects by returning no records and does not visibly append a rejection audit record. |
| Is the write synchronous or queued? | Original ARE bridge writes synchronously. `ARE_SERVER.py` `/ingest` uses FastAPI `BackgroundTasks`, so it returns before the vault append is complete. |
| Is durability confirmed before downstream recall? | Original ARE bridge returns after file append, but no explicit fsync. `ARE_SERVER.py` background ingestion does not confirm durability to the caller. |
| Is chronology globally ordered? | No single global chronology exists. Each store has its own chronology. Original ARE uses timestamp order, `memory_vault.jsonl` uses append order plus `anchored_at`, Sentinel spine uses `ts`, and ARE Spectacle uses SQLite records. |
| What happens during simultaneous requests? | `ARE_SERVER.py` uses background append without an explicit file lock. Original ARE bridge appends directly. SQLite stores rely on SQLite transaction behavior. There is no verified global serialization layer across all memory writes. |

### Document/upload ingest path

The upload and parser path is separate from the governed chat memory path.

Observed path:

1. `claire_gui.py` handles upload.
2. Text is extracted and chunked locally.
3. `ingest_document_chunks(...)` posts chunks to `claire-ingest.service`.
4. `claire_ingest_bridge.py` builds a Sentinel record:
   - `hg_id`
   - `source`
   - `ts`
   - `payload`
   - `domain`
   - `chunk_id`
   - `metadata`
   - `v_sig`
5. The Sentinel record is appended to `/home/LuciusPrime/claire/silo_data/sentinel_spine.jsonl`.
6. The same record is forwarded to `http://127.0.0.1:8002/ingest`.
7. `ARE_SERVER.py` accepts the record and schedules `append_to_vault(data)` as a background task.
8. The durable vault append target is `/home/LuciusPrime/claire/data/memory_vault.jsonl`.
9. `ARE_SERVER.py` indexes the record into in-memory token and exact indexes.

This path is real and persistent, but it is not a hash-linked Truth Spine.

## 4. Authoritative Memory Store

There is no single universal authoritative memory store today.

### Active stores by authority scope

| Store | Path | Technology | Scope | Authority classification |
|---|---|---|---|---|
| ARE Server vault | `/home/LuciusPrime/claire/data/memory_vault.jsonl` | JSONL | Document/upload memory and ARE_SERVER recall | Authoritative for `claire-are.service` |
| Sentinel spine | `/home/LuciusPrime/claire/silo_data/sentinel_spine.jsonl` | JSONL | Parser/Sentinel ingest audit | Authoritative ingest audit for `claire-ingest.service` |
| Original ARE | `/home/LuciusPrime/original_are.pyiginal_are.py/are_data/are_mem.jsonl` | JSONL | Default governed chat memory commit/recall | Authoritative for default `ClaireRuntime` Original ARE path |
| ARE Spectacle DB | `/home/LuciusPrime/are-spectacle-v2/data/spectacle.db` | SQLite | ARE Spectacle v2 local runtime | Authoritative for ARE Spectacle only |
| Runtime trace DB | `/home/LuciusPrime/claire/claire_state/claire_runtime_traces.db` | SQLite | Governed runtime traces | Authoritative trace index for `TraceLogger` |
| Runtime trace JSONL | `/home/LuciusPrime/claire/data/claire_runtime_traces.jsonl` | JSONL | Governed runtime trace append log | Append trace log |
| Session memory | `/home/LuciusPrime/claire/data/session_memory.jsonl` | JSONL | Legacy GUI/session memory | Session/chat support, not canonical ARE |
| SQLite memory store | `/home/LuciusPrime/claire/claire_state/claire_memory.db` | SQLite | Structured memory prototype | Mostly dormant under default `ClaireRuntime` |

### Record counts and sizes

| Path | Records | Size | Oldest | Newest | Notes |
|---|---:|---:|---|---|---|
| `/home/LuciusPrime/claire/data/memory_vault.jsonl` | 8,463 | 9,644,149 bytes | 2026-04-07 | 2026-07-05 | Active ARE Server vault |
| `/home/LuciusPrime/claire/silo_data/sentinel_spine.jsonl` | 8,090 | 8,825,099 bytes | timestamped | timestamped | Active ingest/Sentinel spine |
| `/home/LuciusPrime/original_are.pyiginal_are.py/are_data/are_mem.jsonl` | 9 | 7,837 bytes | timestamped | timestamped | Default governed chat Original ARE path |
| `/home/LuciusPrime/claire/data/session_memory.jsonl` | 5,387 | 3,616,524 bytes | 2026-04-19 | 2026-07-05 | Legacy/session support |
| `/home/LuciusPrime/claire/data/traces.jsonl` | 5,295 | 19,390,387 bytes | 2026-04-20 | 2026-07-10 | Demo/legacy traces |
| `/home/LuciusPrime/claire/data/claire_runtime_traces.jsonl` | 230 | 1,033,990 bytes | runtime trace | runtime trace | Governed runtime traces |
| `/home/LuciusPrime/claire/claire_state/claire_runtime_traces.db` | 230 traces | 1,351,680 bytes | runtime trace | runtime trace | SQLite trace table |
| `/home/LuciusPrime/claire/claire_state/claire_memory.db` | 3 memory events | 57,344 bytes | n/a | n/a | Structured memory store, not default live authority |
| `/home/LuciusPrime/are-spectacle-v2/data/spectacle.db` | 55 durable records | 94,208 bytes | n/a | n/a | ARE Spectacle local store |
| `/home/LuciusPrime/claire/veritas/are_data/are_mem_live.jsonl` | 5,000 | 1,756,586 bytes | n/a | n/a | Veritas/Original-ARE-like store, likely trimmed |

## 5. Derived Indexes and Caches

### ARE_SERVER in-memory indexes

Source: `/home/LuciusPrime/claire/ARE_SERVER.py`

`ARE_SERVER.py` loads `/home/LuciusPrime/claire/data/memory_vault.jsonl` at startup and builds:

- `_RECORDS`
- `_TOKEN_INDEX`
- `_EXACT_INDEX`

These are downstream indexes and can be rebuilt from `memory_vault.jsonl`. They are not persisted as separate authoritative files.

### FAISS / deterministic relevance code

Source: `/home/LuciusPrime/claire/faiss_are_index.py`

`FaissAREIndex` and helper functions build a deterministic relevance helper from Original ARE records. This is downstream and rebuildable. No active persistent FAISS `.index` file was verified as part of the live public runtime.

### ARE Spectacle recall index

Source tree: `/home/LuciusPrime/are-spectacle-v2`

ARE Spectacle uses SQLite durable records and service-layer recall/relevance logic. It is separate from the public GUI memory path and not the single authority for all CLAIRE memory.

### Market/vector data

Market vector JSONL files exist under `/home/LuciusPrime/claire/data/market_memory/`. They are not confirmed as part of the live CLAIRE answer path. Treat as historical/domain-specific derived data unless a running service proves otherwise.

### Answer to: can all indexes be rebuilt from ARE?

Not from one unified ARE today.

Current local indexes can be rebuilt from their own local authorities:

- ARE Server indexes rebuild from `memory_vault.jsonl`.
- FAISS/deterministic Original ARE index rebuilds from Original ARE JSONL.
- ARE Spectacle recall rebuilds from `spectacle.db`.

For Venture Intelligence, the target should be: every vector/search/graph/cluster index rebuilds from a single governed manifest composed of ARE Truth Spine events plus immutable raw-evidence source manifests.

## 6. Current Capacity and Limits

### Disk pressure

The root filesystem is nearly full:

| Filesystem | Mounted at | Size | Used | Available | Use |
|---|---|---:|---:|---:|---:|
| `/dev/nvme0n1p1` | `/` | 29G | 27G | 1.3G | 96% |

This is the biggest immediate capacity risk. The current Azure root disk cannot support a growing Venture Intelligence evidence archive.

### Data directory sizes

| Directory | Approximate size |
|---|---:|
| `/home/LuciusPrime/claire/data` | 103M |
| `/home/LuciusPrime/claire/silo_data` | 15M |
| `/home/LuciusPrime/claire/claire_state` | 1.5M |
| `/home/LuciusPrime/claire/veritas` | 38M |
| `/home/LuciusPrime/are-spectacle-v2/data` | 100K |
| `/home/LuciusPrime/claire_repos/claire-veritas-legal/memory` | 2.4M |
| `/home/LuciusPrime/CLAIRE_AZURE_EVACUATION` | 474M |

### Metadata growth projection

Approximate observed bytes per record:

- `memory_vault.jsonl`: 1,140 bytes/record
- `sentinel_spine.jsonl`: 1,091 bytes/record
- Combined vault + sentinel metadata: 2,231 bytes/ingested record
- `claire_runtime_traces.jsonl`: 4,495 bytes/trace

Projected storage:

| Records | Vault only | Sentinel only | Vault + Sentinel |
|---:|---:|---:|---:|
| 1 million | 1.14 GB | 1.09 GB | 2.23 GB |
| 10 million | 11.4 GB | 10.9 GB | 22.3 GB |
| 100 million | 114 GB | 109 GB | 223 GB |

These numbers exclude raw documents, PDFs, pages, screenshots, model outputs, embeddings, graph indexes, and backups. Raw Venture evidence will dominate storage and must live outside the Azure root disk.

### Retention and trimming

Findings:

- `ARE_SERVER.py` has no verified trim, rotation, archive, fsync, or max-line enforcement in the active service.
- `claire_ingest_bridge.py` appends Sentinel records without visible rotation or fsync.
- Original ARE doctrine includes `max_lines` and RAM watchdog trimming in older code/specs, but the live `original_are_bridge.py` append path does not implement that watchdog.
- `/home/LuciusPrime/claire/veritas/are_data/are_mem_live.jsonl` contains exactly 5,000 records, consistent with a trim/retention limit in an older Veritas/ARE path.
- Standard system timers exist for logrotate and temporary-file cleanup, but no CLAIRE-specific memory cleanup timer was verified.

## 7. Persistence and Restart Behavior

### Survives restart

| Component | Persistence behavior |
|---|---|
| `claire-are.service` | Reloads `memory_vault.jsonl` and rebuilds in-memory indexes at startup. |
| `claire-ingest.service` | Keeps `sentinel_spine.jsonl` on disk. |
| `ClaireRuntime` Original ARE | Reads/writes Original ARE JSONL. |
| `TraceLogger` | Writes both JSONL and SQLite traces. |
| ARE Spectacle | Keeps SQLite `spectacle.db`. |
| Session memory | JSONL file persists but is not a canonical Truth Spine. |

### Does not survive restart as authority

| Component | Behavior |
|---|---|
| ARE Server `_TOKEN_INDEX` and `_EXACT_INDEX` | Rebuilt from `memory_vault.jsonl`; not authoritative. |
| FAISS/deterministic in-memory indexes | Rebuildable; not authoritative. |
| Temporary uvicorn on port `8011` | Test process, not production authority. |

## 8. Integrity Findings

### ARE Server vault

Source: `/home/LuciusPrime/claire/ARE_SERVER.py`

Findings:

- Records are appended as JSONL.
- `_fingerprint(record)` and `_verify_hash` are computed at runtime during load/index.
- `verify(record)` compares a recomputed fingerprint to the runtime `_verify_hash`.
- Because `_verify_hash` is not stored in the durable JSONL record, a modified disk record can be loaded and receive a fresh `_verify_hash` after restart.
- Therefore this is not tamper-evident across restarts.
- `/ingest` writes through `BackgroundTasks`, so a successful response does not prove disk durability.

### Sentinel spine

Source: `/home/LuciusPrime/claire/claire_ingest_bridge.py`

Findings:

- Each record has `v_sig`, derived from payload/domain/source/chunk metadata.
- The file is append-oriented JSONL.
- No previous-record hash chain was verified.
- No fsync was verified.

### Original ARE

Source: `/home/LuciusPrime/claire/original_are_bridge.py`

Findings:

- Stored shape is compatible with Original ARE:

```json
{"ts": 0, "sha": "sha256(text)[:10]", "text": "..."}
```

- Manual read-only verification of the 9 live records found no bad `sha` values.
- The live reader does not visibly enforce checksum validation on recall.
- There is no previous-record hash chain in this implementation.

### ARE Spectacle

Source tree: `/home/LuciusPrime/are-spectacle-v2`

Findings:

- `durable_records` table includes `content_hash`.
- SQLite `quick_check` passed.
- Manual content-hash verification found no bad durable records.
- WriteBarrier exists and commits approved records.
- Rejected writes do not appear to be durably audited as rejection records in the inspected WriteBarrier path.
- No global previous-record hash chain was verified.

### Hardened / plugin-ready Truth Spine code

Source: `/home/LuciusPrime/claire/claire_are/truth_spine.py`

Findings:

- A more durable segmented Truth Spine implementation exists in source.
- It includes stronger flush/fsync and segment mechanics than the live `ARE_SERVER.py` vault.
- It was not verified as the active memory authority for the running `claire-are.service`.

## 9. Duplicate Implementations

The following overlapping memory implementations exist:

| Implementation | Path | Status |
|---|---|---|
| ARE Server JSONL vault | `/home/LuciusPrime/claire/ARE_SERVER.py` | Active for `claire-are.service` |
| Original ARE bridge | `/home/LuciusPrime/claire/original_are_bridge.py` | Active for default governed chat runtime |
| Structured SQLite memory store | `/home/LuciusPrime/claire/are_memory_store.py` and `/home/LuciusPrime/claire/claire_state/claire_memory.db` | Implemented but mostly dormant in default runtime |
| ARE Spectacle v2 | `/home/LuciusPrime/are-spectacle-v2` | Active service, separate store |
| Plugin-ready `claire_are` package | `/home/LuciusPrime/claire/claire_are/` | Source exists; not verified as live authority |
| Session memory JSONL | `/home/LuciusPrime/claire/data/session_memory.jsonl` | Legacy/session support |
| Demo memory SQLite | `/home/LuciusPrime/claire/data/are_demo_memory.sqlite` | Public demo memory, not production authority |
| Veritas ARE/live JSONL | `/home/LuciusPrime/claire/veritas/are_data/are_mem_live.jsonl` | Domain-specific/legacy store |
| Veritas Legal segmented ARE data | `/home/LuciusPrime/claire/data/veritas_legal_are/segments/segment_000000.jsonl` | Legal event store/test slice |

This duplication is the main architectural risk. The names imply one ARE, but live writes are distributed across multiple stores with different durability and integrity properties.

## 10. Missing Layers

Required Venture Memory Design comparison:

| Layer | Status | Finding |
|---|---|---|
| 1. ARE Truth Spine | EXISTS BUT INCOMPLETE | Several append stores exist, but no single active global Truth Spine with durable hash-chain authority for every memory write. |
| 2. Raw Evidence Archive | EXISTS BUT INCOMPLETE | Upload directories and Veritas evidence paths exist, but no verified immutable object/file archive with manifest, retention plan, and source-hash authority for Venture evidence. |
| 3. Recognition Rail | EXISTS BUT UNUSED / DUPLICATED | FAISS/deterministic and lexical relevance helpers exist. No unified rebuildable rail tied to one canonical Truth Spine was verified. |
| 4. Q Insight Working State | EXISTS BUT INCOMPLETE | Orientation/posture concepts exist in runtime and ARE Spectacle, but not verified as a single active Venture working-state layer. |
| 5. Opportunity Ledger | MISSING | No dedicated immutable Venture hypothesis/outcome ledger was verified. |
| 6. LLM Context Assembly | EXISTS BUT INCOMPLETE | `ClaireRuntime` assembles governed context before provider calls; however not all routes are proven to use the same path, and source/memory authority is fragmented. |

## 11. Venture Intelligence Readiness

Current readiness: not sufficient for a growing Venture Intelligence archive without storage and authority expansion.

What works today:

- Persistent JSONL document memory exists.
- Persistent Sentinel ingest audit exists.
- Governed runtime recall-before-provider exists in `ClaireRuntime`.
- Trace logging exists.
- Derived token/exact indexes rebuild from JSONL.
- ARE Spectacle has a separate SQLite governed memory prototype.

What blocks Venture-scale use:

- No single canonical memory write authority across GUI chat, parser ingest, Spectacle, Veritas, and demos.
- Live `memory_vault.jsonl` is not a tamper-evident hash chain across restart.
- `ARE_SERVER.py` accepts writes asynchronously without durability confirmation to the caller.
- Rejected writes are not consistently audited.
- Root disk is 96% full with only about 1.3 GB available.
- No verified immutable raw-evidence archive for large filings, pages, PDFs, snapshots, and external source captures.
- No unified rebuild story for all future search/vector/graph indexes from one Truth Spine plus source manifest.
- No tested backup restoration path for all memory layers.

## 12. Exact Recommended Changes

Do not replace ARE doctrine. Consolidate live writes behind one durable memory spine.

Recommended changes:

1. Designate one canonical live memory authority.
   - Recommended: promote the hardened `claire_are` Truth Spine or equivalent into the live `claire-are.service` path.
   - Preserve Original ARE compatibility by emitting `{ts, sha, text}` projection records for legacy consumers.

2. Make `claire-are.service` a durability-confirming writer.
   - `/ingest` should not report committed until the durable append and manifest/index update are complete.
   - Add explicit failure return when disk write fails.

3. Add global event identity.
   - Every accepted memory event should have `truth_hash` or `are_event_sha`.
   - Parser, Veritas, chat, and Venture records should reference that ID.

4. Make Sentinel rejection auditable.
   - Rejected writes must be durably recorded as rejected events, excluded from normal recall, and visible in audit.

5. Add immutable raw evidence archive.
   - Store full raw evidence outside the Azure root disk.
   - Use content-addressed paths or stable `source_doc_id` plus `source_hash`.
   - Keep raw evidence separate from derived memory text.

6. Move large/archive storage off the root disk.
   - Use object storage, mounted data disk, or another durable external storage target.
   - Keep local hot metadata small and backed up.

7. Define rebuild contracts.
   - All token, vector, graph, Recognition Rail, and Q Insight indexes must rebuild from Truth Spine plus raw-evidence manifests.

8. Add restoration tests.
   - Restore the Truth Spine into a clean GREEN runtime.
   - Rebuild indexes.
   - Run recall, trace, Veritas ingest, and provider-context assembly tests.

## 13. Files That Would Need Modification

No files were modified for implementation during this audit. If approved later, likely modification targets are:

| File | Reason |
|---|---|
| `/home/LuciusPrime/claire/ARE_SERVER.py` | Replace background append with durable Truth Spine write and verified response semantics. |
| `/home/LuciusPrime/claire/claire_ingest_bridge.py` | Ensure Sentinel records receive/return canonical `truth_hash` / `are_event_sha`. |
| `/home/LuciusPrime/claire/claire_runtime.py` | Point governed chat commits and recalls at the canonical Truth Spine service or adapter. |
| `/home/LuciusPrime/claire/original_are_bridge.py` | Keep as compatibility projection, not the isolated chat authority. |
| `/home/LuciusPrime/claire/faiss_are_index.py` | Rebuild from canonical events and source manifests. |
| `/home/LuciusPrime/claire/trace_logger.py` | Ensure trace records reference canonical event hashes. |
| `/home/LuciusPrime/claire/claire_are/truth_spine.py` | Candidate hardened Truth Spine implementation if promoted. |
| `/home/LuciusPrime/are-spectacle-v2/app/...` | Either integrate Spectacle with canonical memory or label it a separate diagnostic/prototype service. |
| Veritas Legal ingest modules | Ensure all evidence records reference `matter_id`, `source_doc_id`, `source_hash`, and canonical ARE event hashes. |

## 14. Safe Migration Plan

This plan does not cut traffic and does not modify Azure BLUE until a separate approval.

1. Freeze nothing yet. Keep BLUE live.
2. Create GREEN isolated storage for canonical Truth Spine.
3. Snapshot current memory stores read-only:
   - `memory_vault.jsonl`
   - `sentinel_spine.jsonl`
   - Original ARE JSONL
   - runtime traces JSONL/SQLite
   - ARE Spectacle SQLite
   - Veritas Legal memory/evidence stores
4. Import snapshots into GREEN canonical event format.
5. Preserve original source identifiers:
   - source path
   - source hash
   - old store name
   - old record offset or row id
   - imported `truth_hash`
6. Rebuild GREEN indexes from canonical events.
7. Run integrity checks:
   - chain verification
   - record counts
   - source-hash consistency
   - rejected-event exclusion from recall
   - recall-before-provider trace test
8. Run parallel request comparison against BLUE.
9. Only after GREEN passes validation, plan a brief coordinated final snapshot for live-changing files.
10. Do not switch traffic until Steve explicitly approves.

## 15. Rollback Plan

If GREEN canonical memory migration fails:

1. Leave BLUE untouched and serving existing traffic.
2. Disable only GREEN test endpoints.
3. Keep imported GREEN data for forensic comparison.
4. Revert GREEN code changes to the last known passing branch.
5. Continue using existing BLUE memory paths:
   - GUI on port `8000`
   - `claire-are.service` on port `8002`
   - `claire-ingest.service` on port `8081`
   - ARE Spectacle on port `8010`
6. Do not delete source snapshots or local live stores.
7. Re-run archaeology checks before attempting a second migration.

## Final Conclusion

C. Existing architecture is only a prototype and needs a durable storage tier.

Reason: an authoritative memory path can be verified, and multiple stores do persist across restart, but the live system is fragmented across several authorities, lacks one globally ordered tamper-evident Truth Spine for all writes, does not consistently audit rejected writes, returns success before durable writes in the ARE Server ingest path, and has insufficient local disk capacity for a growing Venture Intelligence evidence archive.
