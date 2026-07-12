# Venture Live Container Pipeline Proof

## 1. Environment
- Host: Azure CLAIRE VM
- Workspace: `/home/LuciusPrime/claire`
- Branch: `codex/venture-intelligence-slice-1`
- Commit at run time: `49fb1b4`
- Deployment: Docker Compose stack running locally on port `8030`

## 2. Running Container List
```text
NAME                   IMAGE                  COMMAND                  SERVICE       CREATED         STATUS         PORTS
claire-minio-1         minio/minio:latest     "/usr/bin/docker-ent…"   minio         Up 4 minutes   0.0.0.0:9000-9001->9000-9001/tcp
claire-neo4j-1         neo4j:5                "tini -g -- /startup…"   neo4j         Up 4 minutes   0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp
claire-postgres-1      postgres:16            "docker-entrypoint.s…"   postgres      Up 4 minutes   0.0.0.0:5433->5432/tcp
claire-qdrant-1        qdrant/qdrant:latest   "./entrypoint.sh"        qdrant        Up 4 minutes   0.0.0.0:6333->6333/tcp
claire-redis-1         redis:7                "docker-entrypoint.s…"   redis         Up 4 minutes   0.0.0.0:6380->6379/tcp
claire-venture-api-1   claire-venture-api     "uvicorn claire_vde.…"   venture-api   Up 4 minutes   0.0.0.0:8030->8030/tcp
```

## 3. Pre-Run Health State
```json
{"status":"ok","truth_spine":{"valid":true,"records":0,"previous_hash":"0"},"database":"/data/venture/venture_intelligence.sqlite","doctrine":"ARE Truth Spine is authority; metadata and indexes are downstream."}
```

Mounted data before the run:
```text
/data/are:
drwxr-xr-x 3 root root 4.0K Jul 12 07:40 segments

/data/venture:
-rw-r--r-- 1 root root 88K Jul 12 07:40 venture_intelligence.sqlite
```

SQLite pre-run counts:
```json
{
  "admission_claims": 0,
  "admitted_evidence": 0,
  "collector_runs": 0,
  "collector_state": 0,
  "opportunity_events": 0,
  "projection_events": 0,
  "reconciliation_state": 0
}
```

## 4. Exact Live API Request
Route:
- `POST /v1/venture/federal-register/run`

Request body:
```json
{
  "query": "artificial intelligence",
  "cutoff_date": "2024-01-01",
  "per_page": 2,
  "max_pages": 1,
  "admit": true,
  "retries": 3,
  "connect_timeout_s": 5,
  "read_timeout_s": 30,
  "respectful_delay_s": 0.2,
  "backoff_base_s": 0.5,
  "version": "federal_register_collector_v1",
  "user_agent": "CLAIRE Venture Intelligence Federal Register Collector/1.0 (respectful; contact local-dev)"
}
```

Exact command:
```bash
curl -sS -D /tmp/fr_headers.txt -o /tmp/fr_response.json -w '%{http_code}' \
  -X POST http://127.0.0.1:8030/v1/venture/federal-register/run \
  -H 'Content-Type: application/json' \
  --data '{"query":"artificial intelligence","cutoff_date":"2024-01-01","per_page":2,"max_pages":1,"admit":true,"retries":3,"connect_timeout_s":5,"read_timeout_s":30,"respectful_delay_s":0.2,"backoff_base_s":0.5,"version":"federal_register_collector_v1","user_agent":"CLAIRE Venture Intelligence Federal Register Collector/1.0 (respectful; contact local-dev)"}'
```

HTTP status:
```text
200
```

Retrieval timestamp:
```text
2026-07-12T07:57:23Z
```

## 5. Federal Register Response
Official endpoint used by the collector:
- `https://www.federalregister.gov/api/v1/documents.json`

The live response returned two admitted evidence items and no errors. The first run admitted:
- `2026-14086` from `https://www.federalregister.gov/documents/2026/07/13/2026-14086/...`
- `2026-14057` from `https://www.federalregister.gov/documents/2026/07/13/2026-14057/...`

Collector metadata included:
- collector: `federal_register`
- collector_version: `federal_register_collector_v1`
- domain: `AI_AGENT_GOVERNANCE`
- query: `artificial intelligence`
- cutoff: `2024-01-01`
- result_count: `2`
- pages_fetched: `1`

## 6. Admitted Evidence
First run admitted evidence:
```json
[
  {
    "title": "Statistical Policy Directive No. 8: North American Industry Classification System (NAICS)-Request for Comments on Proposed Updates for 2027",
    "source": "federal_register",
    "collector": "federal_register",
    "are_hash": "bb67c765707c3c7b5c29f05bb57187715d47dcff1f2f38cd7e65b0acd9e69d26",
    "checksum": "ea1e80d9000b21fb0060aae4bf16abb84d53d5a0f449dc811c52e746ddcfcf8b",
    "provenance_url": "https://www.federalregister.gov/documents/2026/07/13/2026-14086/statistical-policy-directive-no-8-north-american-industry-classification-system-naics-request-for"
  },
  {
    "title": "FY 2026 Job Placement and Training-Native American Technology and Manufacturing Grant Pilot Program (IGNITE: Indigenous Growth in New & Innovative Trade Employment); Solicitation of Proposals",
    "source": "federal_register",
    "collector": "federal_register",
    "are_hash": "dc1d947c3dfe38991628f319b50a890b216e5d17ad8d370d7814e8f438260cca",
    "checksum": "c1e6328f4d4116454a4005e8b0dde64eefb030e0f1c3c124eb5351fe7772fc7f",
    "provenance_url": "https://www.federalregister.gov/documents/2026/07/13/2026-14057/fy-2026-job-placement-and-training-native-american-technology-and-manufacturing-grant-pilot-program"
  }
]
```

Second run admitted evidence:
```json
[
  {
    "title": "Proposed Information Collection; ATUS Artificial Intelligence (AI) Questions",
    "source": "federal_register",
    "collector": "federal_register",
    "are_hash": "4a6470e02a46c948dc911e72a80b332f9c35928d9e242b7d6a5d3bef31863839",
    "checksum": "c4a6e274f8d06c451a2e57f844bd609829715ff52a078a2318fd6d263c79480d",
    "provenance_url": "https://www.federalregister.gov/documents/2026/07/10/2026-13928/proposed-information-collection-atus-artificial-intelligence-ai-questions"
  },
  {
    "title": "Anti-Money Laundering and Countering the Financing of Terrorism Programs",
    "source": "federal_register",
    "collector": "federal_register",
    "are_hash": "8f7fc21f0592ca9e762a832ee5e3d9714e7f98dccfdbfb3fee65c2a1e1696bd9",
    "checksum": "b79b4612d1571df4467f5b5267cb19558ce1308215c9109df700be78fc8867b3",
    "provenance_url": "https://www.federalregister.gov/documents/2026/07/09/2026-13919/anti-money-laundering-and-countering-the-financing-of-terrorism-programs"
  }
]
```

## 7. Canonical ARE Event Hashes
Canonical ARE hashes observed in the live deployment:
- `bb67c765707c3c7b5c29f05bb57187715d47dcff1f2f38cd7e65b0acd9e69d26`
- `dc1d947c3dfe38991628f319b50a890b216e5d17ad8d370d7814e8f438260cca`
- `4a6470e02a46c948dc911e72a80b332f9c35928d9e242b7d6a5d3bef31863839`
- `8f7fc21f0592ca9e762a832ee5e3d9714e7f98dccfdbfb3fee65c2a1e1696bd9`

## 8. Post-Run Health State
```json
{"status":"ok","truth_spine":{"valid":true,"records":6,"previous_hash":"9b16ed4b1ffc0923a429cc34ebd0e347b09c556e712d708746c58f4f578550fc"},"database":"/data/venture/venture_intelligence.sqlite","doctrine":"ARE Truth Spine is authority; metadata and indexes are downstream."}
```

Post-run SQLite counts:
```json
{
  "admission_claims": 4,
  "admitted_evidence": 4,
  "collector_runs": 2,
  "collector_state": 1,
  "opportunity_events": 0,
  "projection_events": 0,
  "reconciliation_state": 1
}
```

## 9. Duplicate-Rerun Proof
The same live Federal Register route was invoked a second time with the same query and the persisted collector state. It continued from the stored cursor and admitted a different pair of records. The already-admitted records were not duplicated.

Observed duplicate protection signals:
- `admitted_evidence` increased from 2 to 4, not 6 or more from re-inserting the first pair
- `opportunity_events` stayed at 0
- `collector_state.last_cursor` advanced to page 3
- existing rows retained their original `are_hash` values

## 10. Reconciliation Result
Exact command:
```bash
curl -sS -X POST http://127.0.0.1:8030/v1/venture/reconcile-orphans
```

HTTP status:
```text
200
```

Response:
```json
{
  "status": "ok",
  "checkpoint_before": 0,
  "checkpoint_after": 6,
  "scanned": 4,
  "repaired": 0,
  "skipped": 4,
  "errored": 0,
  "errors": []
}
```

## 11. Container Logs
Relevant `venture-api` log lines:
```text
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8030 (Press CTRL+C to quit)
INFO:     172.19.0.1:44330 - "GET /v1/venture/health HTTP/1.1" 200 OK
INFO:     172.19.0.1:56006 - "POST /v1/venture/federal-register/run HTTP/1.1" 200 OK
INFO:     172.19.0.1:51524 - "POST /v1/venture/federal-register/run HTTP/1.1" 200 OK
INFO:     172.19.0.1:49954 - "POST /v1/venture/reconcile-orphans HTTP/1.1" 200 OK
```

No container restarted or crashed during the proof.

## 12. Live Mounted Data Verification
The running container had:
- `/data/are/segments`
- `/data/venture/venture_intelligence.sqlite`

SQLite schema included:
- `admitted_evidence`
- `admission_claims`
- `collector_runs`
- `collector_state`
- `opportunity_events`
- `projection_events`
- `reconciliation_state`

The stored evidence rows referenced canonical ARE hashes in the `are_hash` column.

Truth Spine verification remained valid throughout the proof via the live health endpoint.

## 13. Known Limitations
- The Federal Register route uses persisted collector state, so repeated invocations continue from the stored cursor rather than replaying the same page again.
- No Opportunity Ledger event was created, which is correct for this evidence slice.
- Reconciliation completed cleanly with zero repairs.

## 14. Exact Commands Used
Representative commands used for proof:
```bash
curl -fsS http://127.0.0.1:8030/openapi.json
curl -fsS http://127.0.0.1:8030/v1/venture/health
sudo docker compose -f docker-compose.venture.yml ps
sudo docker compose -f docker-compose.venture.yml exec -T venture-api ls -lah /data/are /data/venture
sudo docker compose -f docker-compose.venture.yml exec -T venture-api python3 - <<'PY'
...
PY
curl -sS -X POST http://127.0.0.1:8030/v1/venture/federal-register/run -H 'Content-Type: application/json' --data '{...}'
curl -sS -X POST http://127.0.0.1:8030/v1/venture/reconcile-orphans
sudo docker compose -f docker-compose.venture.yml logs --no-color --tail=300 venture-api
```

## Final Statements
The live containerized Federal Register collector was invoked through the API: YES

The official Federal Register API returned real records: YES

The running containerized Truth Spine record count increased above zero: YES

The admitted evidence is API-readable: YES

The stored evidence references canonical ARE hashes: YES

The duplicate rerun was idempotent: YES

The Opportunity Ledger correctly created or withheld an event: YES

The reconciliation endpoint completed successfully: YES

The running deployment remained healthy: YES

The live containerized public-source pipeline is verified through: official Federal Register API -> live Venture API -> admission into ARE Truth Spine -> persisted SQLite metadata -> duplicate-safe rerun -> reconciliation endpoint
