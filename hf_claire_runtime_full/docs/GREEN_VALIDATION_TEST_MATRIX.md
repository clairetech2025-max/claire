# GREEN Validation Test Matrix

Date: 2026-07-11

## Empty-State Validation Results

| Component | Test | Expected Result | Observed Result | Status |
|---|---|---|---|---|
| Git source | Branch and commit check | `codex/huggingface-portable-demo` at `57687656cd55ca27b6b9c2a16b933b4e535d2f40` | matched local and `origin` | PASS |
| Python deps | Fresh `/tmp` venv install | install succeeds without Azure venv | install succeeded | PASS |
| Python modules | `py_compile` key modules | no syntax/import compile errors | passed | PASS |
| GO backend | `go build main.go` | binary builds from clean clone | `/tmp/green-clean-base/claire-go-clean` built | PASS |
| ARE | `GET /health` on isolated port `19002` | HTTP 200 | `{"status":"online","mode":"ARE_FAST_INDEXED","vault_records":0,...}` | PASS |
| Ingest bridge | `GET /health` on `19081` | HTTP 200 | `{"ok":true,"service":"claire-ingest",...}` | PASS |
| GO backend | `GET /health` on `19080` | HTTP 200 | `{"addr":"127.0.0.1:19080","ok":true,"service":"claire-go"}` | PASS |
| CLAIRE adapter | `GET /health` on `19000` | HTTP 200 | `{"status":"ok","service":"Claire Runtime Full"}` | PASS |
| CLAIRE status | `GET /status` | dependencies online | ARE/LLM/ingest online, private full build | PASS |
| ARE recall | ingest then query | recall returns test memory | returned `GREEN empty-state smoke memory` | PASS |
| Ingest bridge | `POST /ingest` | bridge pushes to ARE | returned `ok:true` with ARE success | PASS |
| Veritas Legal | upload synthetic TXT then `POST /veritas-legal/run` | source hash, source ID, ARE event, metadata, trace | organized 1 evidence file; emitted `source_doc_id`, `source_sha256`, `are_event_sha`, legal metadata paths | PASS |
| Demo mode API | `POST /reply` with demo mode | structured trace JSON | returned required demo JSON with trace_id, recall, policy, decision, output | PASS |
| Empty state | generated files | only under isolated runtime dir | files generated under `/tmp/green-clean-base/runtime_data` | PASS |
| Safety | BLUE | no stop, route change, deletion, or cutover | no BLUE modification performed | PASS |

## Known Blockers

- `hf` CLI is not on PATH in this shell, so the Hugging Face Space metadata was not confirmed via CLI.
- Docker image build was not rerun in this phase. Prior local Docker build attempts were blocked by low root disk space.
- Model/provider health is only endpoint-level in this empty-state test. No paid/private model secret was injected.
- Lane A and Lane B restored-data validation has not started.

## Validation Scope

This proves clean-base empty-state rebuild from source. It does not yet prove restored memory/database/evidence portability.
