# Security

## Data Handling

Do not commit:

- `.env` files
- API keys, access tokens, passwords, private keys, or certificates
- SQLite databases or unrestricted database dumps
- private legal evidence, uploads, indexes, or runtime logs
- local model weights

Runtime databases such as `claire_state/claire_memory.db` and
`claire_state/claire_runtime_traces.db` are local state. They should be backed up
privately and recreated or mounted at deployment time, not published as source.

## Runtime Policy

- EchoShield classifies hostile or sensitive context.
- Sentinel makes pre-action authorization decisions.
- 3CRP records memory-write and egress authorization.
- Durable ARE writes fail closed when authorization is denied.
- Truth Spine records provenance and verifies event-chain integrity.

## Hosted Demo Rules

Hugging Face Spaces should use sanitized demo data by default. Public Spaces must
not bundle private evidence, live databases, customer records, secrets, or
Azure-only configuration.

## Secret Scan

Before pushing, scan tracked files and deployment trees for secret-like strings:

```bash
python scripts/security_scan.py
```

GitHub also runs `.github/workflows/security-source-scan.yml` on pushes, pull
requests, and manual dispatches. The scan intentionally fails on token-shaped
values, private keys, Azure connection strings, database files, logs, uploads,
evidence folders, indexes, and other private runtime artifacts in tracked
source.

If a real secret appears in Git history, rotate it and remove it from history
before publishing. Current-tree cleanup alone is not a substitute for rotation
when a credential may have been exposed.
