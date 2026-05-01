ARE Spectacle
=============

ARE Spectacle is a local governed-memory runtime for AI systems.

It is not Claire and does not require Claire.
It runs on your computer as a local API server.

Start
-----

1. Double-click ARE-Spectacle.exe.
2. Wait for the console window to say the server has started.
3. Open:

   http://127.0.0.1:8010/health

The app stores local runtime data in a data folder beside the executable.

API
---

GET  /health
POST /ingest
POST /query
GET  /gyro
POST /prompt-prefix
GET  /trace/{trace_id}
GET  /report/{trace_id}

Example PowerShell
------------------

Invoke-RestMethod -Uri "http://127.0.0.1:8010/health"

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/ingest" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"text":"ARE Spectacle stores governed recall outside the model with provenance and trace replay.","source_ref":"buyer-demo","session_id":"demo"}'

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/query" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"What role does provenance play in governed memory?","session_id":"demo"}'

Notes
-----

This product is a governed memory and trace runtime. It does not perform real-world actions.
Keep the executable folder together. If Windows Firewall prompts you, allow local/private access.
