# Security

## Data Handling

Do not commit:

- `.env` files
- API keys, access tokens, passwords, private keys, or certificates
- SQLite databases or unrestricted database dumps
- private legal evidence, uploads, indexes, or runtime logs
- local model weights

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

Before pushing, scan changed files and deployment trees for secret-like strings.
If a real secret appears in Git history, rotate it and remove it from history
before publishing.
