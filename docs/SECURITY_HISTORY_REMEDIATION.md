# Security History Remediation

This runbook covers historical secret-shaped findings after the current tracked
tree has already been sanitized.

Do not rewrite shared Git history until all steps below are approved. Do not
print secret values in tickets, logs, screenshots, reports, or chat.

## Current Findings

Run the redacted scanner:

```bash
python scripts/security_history_scan.py --json --report-only
```

Latest known findings:

| Commit | Path | Line | Kind | Assessment |
| --- | --- | ---: | --- | --- |
| `3e6ad3f34d8cc06c5363e0d803d5b59bf67bdea5` | `tests/test_security_scan.py` | 20 | `openai_api_key` | Scanner fixture literal, now removed from HEAD |
| `3e6ad3f34d8cc06c5363e0d803d5b59bf67bdea5` | `tests/test_security_scan.py` | 21 | `huggingface_token` | Scanner fixture literal, now removed from HEAD |
| `3e6ad3f34d8cc06c5363e0d803d5b59bf67bdea5` | `tests/test_security_scan.py` | 22 | `github_token` | Scanner fixture literal, now removed from HEAD |
| `3e6ad3f34d8cc06c5363e0d803d5b59bf67bdea5` | `tests/test_security_scan.py` | 24 | `azure_connection_string` | Scanner fixture literal, now removed from HEAD |
| `3e6ad3f34d8cc06c5363e0d803d5b59bf67bdea5` | `tests/test_security_scan.py` | 27 | `private_key` | Scanner fixture literal, now removed from HEAD |
| `3648607d1418cf777e66faf008744760d39b83ef` | `claire_azure_sync.py` | 1 | `azure_connection_string` | Removed from HEAD; treat as exposed until proven placeholder-only |

## Required Decisions

Before remediation, decide and record:

- Whether the Azure-looking value was ever a live credential.
- Which Azure storage account or environment it could have reached.
- Whether any dependent key, token, or connection string must be rotated.
- Whether shared branches may be rewritten.
- Who must refresh local clones after the rewrite.
- Whether GitHub, Hugging Face, Azure, or other caches need purge requests.

## Rotation First

If any finding may be live, rotate it before rewriting history:

1. Revoke or rotate the exposed credential in its provider console.
2. Replace production and staging secrets through the hosting secret stores.
3. Verify current services still start without using the old value.
4. Record only secret names, provider, timestamp, and owner. Never record values.

## Approved History Rewrite

Use a fresh mirror clone, not the active working tree:

```bash
git clone --mirror https://github.com/clairetech2025-max/claire.git claire-history-cleanup.git
cd claire-history-cleanup.git
```

Remove the known paths or rewrite matching content with an approved tool such as
`git filter-repo`. Example path removal:

```bash
git filter-repo --path claire_azure_sync.py --invert-paths
```

If rewriting the short-lived scanner fixture commit, rewrite only the affected
test-file blob or remove that commit from rewritten history according to the
approved plan.

After rewriting:

```bash
git fsck --full
git log --all -- tests/test_security_scan.py claire_azure_sync.py
```

Clone the rewritten repository into a clean directory and run:

```bash
python -m venv venv
venv/bin/python -m pip install -e .
venv/bin/python scripts/security_scan.py
venv/bin/python scripts/security_history_scan.py --json
venv/bin/python -m pytest
```

Only after the clean clone passes, push with explicit approval:

```bash
git push --force-with-lease --all origin
git push --force-with-lease --tags origin
```

## Aftercare

After a history rewrite:

- Tell collaborators to reclone or hard-reset to the rewritten branch.
- Re-run `Security Source Scan`.
- Re-run `Security History Scan`.
- Re-run `Validate Hugging Face Packages`.
- Re-run `Hugging Face Deployment Readiness`.
- Preserve the pre-rewrite bundle privately for legal/audit continuity.
- Do not deploy to Hugging Face until source and history scans are understood.

## Non-Goals

This runbook does not:

- rotate credentials automatically;
- rewrite history automatically;
- delete preservation bundles;
- alter Azure;
- upload to Hugging Face;
- certify that historical credentials were never valid.
