# Real Execution Path Audit

Branch: `fix/real-machine-routing-and-trace`
Baseline commit: `26b0455dac30dc0319913df421bd17ea41b5df9b` (main, unmodified)

Method: every flow below was traced by reading the actual button element, its
JS event listener, the fetch call it issues, the FastAPI route it hits, and
the Python function(s) that route calls, down to the point where real
work either does or does not happen. Nothing here is inferred from names or
UI copy alone.

---

## 1. Speed Test ("ARE recall proof")

| Stage | Location |
|---|---|
| Button | `id="areSpeedBtn"`, `claire_gui.py:3325-3329` |
| Click handler | `claire_gui.py:6699-6703` → calls `launchMemoryPerformanceDemo()` |
| Handler function | `launchMemoryPerformanceDemo()`, `claire_gui.py:5948-5986` |
| Endpoint called | `GET /reply?q=...&demo=true&demo_scenario=memory_speed` (`claire_gui.py:5963`) |
| Backend route | `@app.get("/reply")`, `claire_gui.py:14828-14842` |
| Route logic | `demo_scenario` query param is **accepted but never forwarded** — `claire_gui.py:14840` calls `build_governed_demo_payload(q, session_id="gui-reply-get")` with only `q`/`session_id`. `demo_scenario=memory_speed` is silently dropped. |
| Service function | `build_governed_demo_payload()`, `claire_gui.py:12762-12781` → `CLAIRE_GOVERNED_RUNTIME.handle_user_message(metadata={"demo_mode": True})` |
| Machine/engine function actually invoked | Because `metadata["demo_mode"]` is set, `ClaireRuntime.handle_user_message()` (`claire_runtime.py:111`) immediately reroutes to `handle_demo_message()` (`claire_runtime.py:1234-1373`) at line 119-120. Inside it: `_recall_demo_memory()` (`:2014-2027`) → real read of the ARE JSONL file via `read_original_are_history()` (`original_are_bridge.py`); `call_nemotron()` (`:1304`) → real LLM call, same adapter/timeout as production. |
| Trace creation | `handle_demo_message()` generates its own `trace_id = new_trace_id()` (`:1243`), persists via `self._persist_demo_trace()` (`:1354`, writes to the separate `public_demo.sqlite` store) and `self.trace_logger.log()` (`:1355`, the real `TraceLogger`). |
| Response field used for "Machine Called" | **None exists.** `handle_demo_message()`'s returned dict contains only `trace_id, demo_mode, identity, input_received, recall_check, policy_validation, decision, output, trace_summary` (`:1324-1342`) — no field the client could read to determine whether the model/tool ran. |
| Confirmed unreachable code | A different function, `build_demo_payload()` (`claire_gui.py:10671-10744+`), *does* measure real elapsed time (`elapsed_ms(total_start)`) and *does* populate a `live_proof` object with `document`, `pipeline`, `speed_proof` sub-objects — exactly what the button's renderer expects. But its only two callers (`claire_gui.py:10844`, `:10924`) feed a separate legacy **text**-command reply path, not `/reply`. It is not reachable from this button's request. |
| Renderer | `memoryPerformanceVisualWorkspace()`, `claire_gui.py:5197-5264` — reads `data.live_proof.memory_performance` / `.speed_proof`; since that key is absent from the actual response, every displayed number (document fetch ms, ARE lookup ms, speedup ×, SHA-256, pipeline ms) falls through to its `\|\| 0` / `\|\| ""` JS default. |
| `machineCalled` in this flow's JS | Hardcoded literal `"NO"` at all three `setWorkflowDebug` call sites: `claire_gui.py:5959`, `:5971`, `:5982`. Never computed from `data`. |

**Verdict:** real ARE file read + real LLM call happen server-side, but the specific "speed proof" metrics the button promises are structurally never populated on this path, and `Machine Called` is a constant regardless of outcome.

---

## 2. Archimedes

| Stage | Location |
|---|---|
| Button | `id="archimedesDemoBtn"`, `claire_gui.py:3415` |
| Click handler | `claire_gui.py:6694-6698` → `launchArchimedesDemo()` |
| Handler function | `claire_gui.py:5908-5946` |
| Endpoint called | `GET /reply?q=Run+Project+ARCHIMEDES+DARPA+presentation+proof+package&demo=true&demo_scenario=archimedes` (`:5923`) |
| Backend route | Same `@app.get("/reply")` as Speed Test. `is_demo_key_query()` (`:9401-9434`) requires an **exact** string match after cleaning (`_clean_for_match`, `:210-212`, lowercases/strips punctuation only — no keyword extraction). The actual prompt sent does not match any of the exact phrases in that set (`"archimedes demo"`, `"darpa archimedes demo"`, etc.), so `is_demo_key_query(q)` is `False` and the request follows the identical `build_governed_demo_payload()` path as Speed Test. |
| Machine/engine function | Same as Speed Test: `handle_demo_message()` (`claire_runtime.py:1234`) — real ARE read + real LLM call, no `live_proof`. |
| Trace creation | Same as Speed Test. |
| `machineCalled` | Hardcoded `"NO"` at `claire_gui.py:5919`, `:5931`, `:5942`. |
| Renderer | `renderArchimedesVisual()` reads `data.live_proof.archimedes` (`claire_gui.py:5064`) — absent from the response for the same reason as Speed Test. |

**Verdict:** identical structural gap to Speed Test — same missing `live_proof`, same hardcoded `machineCalled`.

---

## 3. ARE Spectacle ("glasses" demo)

| Stage | Location |
|---|---|
| Button | `id="glassesDemoBtn"`, `claire_gui.py:3414` |
| Click handler | `claire_gui.py:6653-6693` |
| Endpoint called | `GET /reply?q=Show+how+The+ARE+Spectacle+improves+an+AI+answer.&demo=true&demo_scenario=glasses` (`:6669`) |
| Backend route | Same `@app.get("/reply")`. Prompt does not exact-match any phrase in `is_demo_key_query()`'s set (checked directly: `"show how the are spectacle improves an ai answer"` is not in the set), so again routes to `build_governed_demo_payload()` → `handle_demo_message()`. |
| Machine/engine function | Same `handle_demo_message()` path as the two above. |
| `machineCalled` | Hardcoded `"NO"` at `claire_gui.py:6665`, `:6677`, `:6688`. |
| Renderer | `renderAreSpectacleVisual()` — not individually re-checked for its exact `live_proof` sub-key this pass, but structurally the same gap applies: `handle_demo_message()` never emits `live_proof` at all, for any scenario. |

**Verdict:** same structural gap as the two flows above.

---

## 4. Veritas packet generation ("Run Veritas Legal")

This flow is materially different from the three above — it is **not** a `demo=true` request and does not go through `ClaireRuntime` at all.

| Stage | Location |
|---|---|
| Button | `id="veritasLegalBtn"`, `claire_gui.py:3313` |
| Click handler | `claire_gui.py:6648` → `runVeritasLegal()`, `claire_gui.py:6542-6598` |
| Endpoint called | `POST /veritas-legal/run`, body `{"mode": "latest_upload"}` (`:6560-6564`) |
| Backend route | `@app.post("/veritas-legal/run")`, `claire_gui.py:15823-15824` |
| Machine/engine function actually invoked | Real. Confirmed by reading the handler body (`claire_gui.py:15823-~15900`): it instantiates `EvidenceEngine(run_state_dir, matter_id=matter_id)` (imported at `claire_gui.py:50` from the `veritas_legal` module) and `claire_parser.ClaireParser(...)` — a genuine "hardened parser" with OCR enabled (`enable_ocr=True`) — then calls `parser.parse_tree(path)` and `engine.ingest_parser_jsonl(...)` against real locally-uploaded files. It fails closed with explicit `503`/`400` JSON responses if `EvidenceEngine`, the parser, or uploaded evidence are unavailable — no silent canned success. |
| Trace creation | `trace_id = _veritas_trace_id()` generated at the top of the handler (`:15824` area); results are written under `Path(VERITAS_LEGAL_STATE_DIR) / trace_id`. |
| `machineCalled` in this flow's JS | Still hardcoded `"NO"` at `claire_gui.py:6556`, `:6590` — **even though this is the one flow confirmed this session to do genuine, non-demo machine work** (real OCR parsing of real uploaded files). This is the flow where the hardcoded value is most clearly wrong, not just incomplete. |

**Verdict:** this is a real execution path, not a demo path — the parser and evidence engine genuinely run. The only defect here is purely cosmetic: `machineCalled` is hardcoded `"NO"` regardless of the real work that happened.

---

## 5. Replay / trace inspection

| Stage | Location |
|---|---|
| Button | `id="traceProofBtn"`, `claire_gui.py:3335-3339` |
| Click handler | `claire_gui.py:6708` → `replayLatestTrace()`, `claire_gui.py:5607-5616`, which calls `replayTrace(lastTraceId)` |
| Handler function | `replayTrace(traceId)`, `claire_gui.py:5598-5605` |
| Endpoint called | `GET /trace/{trace_id}` (`:5600`) |
| Backend route | `@app.get("/trace/{trace_id}")`, `claire_gui.py:14979-15010` |
| Machine/engine function | Real, tiered lookup: (1) `_public_demo_fetch_trace(trace_id)` against `public_demo.sqlite`; (2) if empty and `CLAIRE_GOVERNED_RUNTIME` is present, `CLAIRE_GOVERNED_RUNTIME.get_trace(trace_id)`; (3) fallback to the JSONL `TRACE_LOG` file scan. No synthetic/placeholder trace is fabricated — a request for an unknown ID returns `404 {"status": "not_found", ...}`. |
| `machineCalled` | **Not applicable — this flow does not call `setWorkflowDebug` at all.** No hardcoded value to correct here; it simply isn't part of the debug HUD. |

**Verdict:** real trace lookup, fails honestly on unknown IDs, no `machineCalled` involvement.

---

## Summary table

| Flow | Real machine work? | `live_proof`/metrics populated? | `machineCalled` correct? |
|---|---|---|---|
| Speed Test | Partial (real ARE read + real LLM call, no timing/hash proof) | No — code that would exists (`build_demo_payload`) but is unreachable from this route | No — hardcoded `"NO"` |
| Archimedes | Partial, same shape as Speed Test | No, same reason | No — hardcoded `"NO"` |
| ARE Spectacle | Partial, same shape | No, same reason | No — hardcoded `"NO"` |
| Veritas Legal | **Yes, fully real** (OCR parser + evidence engine on real uploaded files) | N/A (different response shape, not `live_proof`-based) | No — hardcoded `"NO"` despite real work |
| Replay/Trace | **Yes, fully real** (tiered real trace lookup) | N/A | N/A — flow doesn't set this field |

**Root cause common to the first three flows:** the GET `/reply` handler's `demo` branch (`claire_gui.py:14837-14840`) never forwards `demo_scenario` into `build_governed_demo_payload()`, and that function always calls `ClaireRuntime.handle_user_message()` with `metadata={"demo_mode": True}`, which unconditionally reroutes to `handle_demo_message()` (`claire_runtime.py:119-120`) — a method that never builds a `live_proof` object for *any* scenario. The scenario-aware, timing-aware code that would populate it (`build_demo_payload()`, `claire_gui.py:10671`) exists but is wired only to a legacy text-command path.

**Root cause common to all five flows' `machineCalled` field:** it is a JS object-literal constant at each `setWorkflowDebug()` call site, not derived from any response field, because no response field carrying that signal exists on the server side (`handle_demo_message()`'s dict and `/veritas-legal/run`'s dict both lack one).
