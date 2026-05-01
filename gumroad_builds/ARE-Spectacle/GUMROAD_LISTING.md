# ARE Spectacle

Governed memory runtime for AI systems.

ARE Spectacle gives builders a local API for memory intake, lane-governed recall, relevance gating, Sentinel-style policy checks, prompt-prefix construction, trace IDs, and replayable reports.

It is not a chatbot. It is the control layer that helps decide what memory is allowed, what memory is relevant, what gets committed, and how the path can be replayed.

## Included

- Windows executable
- Local FastAPI runtime
- SQLite-backed durable records
- Sample API requests
- Buyer start guide

## API

- `GET /health`
- `POST /ingest`
- `POST /query`
- `GET /gyro`
- `POST /prompt-prefix`
- `GET /trace/{trace_id}`
- `GET /report/{trace_id}`

## Positioning

Use ARE Spectacle as a governed-memory layer beside your AI app. Keep the model focused on generation while Spectacle handles routing, recall discipline, traceability, and replay.

## Important

ARE Spectacle runs locally and does not perform real-world actions. It is a memory governance and trace runtime for AI development and evaluation.
