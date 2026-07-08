# CLAIRE Runtime Full - Hugging Face Migration Scaffold

This folder is a scaffold for a separate Hugging Face Docker Space named `Blackstormhorse/CLAIRE_Runtime_Full`.

It is not the public lightweight control demo and it does not contain private runtime state.

## Purpose

Run the real CLAIRE FastAPI runtime from the Azure trunk on Hugging Face without copying secrets, private memory, runtime databases, legal files, generated indexes, or Azure-specific state.

## Space Type

Use a Docker Space. The current runtime uses FastAPI, uvicorn, local files, background/service bridges, and custom routes, so a plain Gradio Space is not the right target.

## What This Scaffold Does

- Clones the real CLAIRE GitHub repo at build time.
- Imports `claire_gui:app` through `hf_runtime_adapter.py`.
- Starts uvicorn on the Hugging Face `PORT`.
- Redirects new runtime memory/trace paths into `/data/claire_runtime` when persistent storage is enabled.
- Leaves all secrets to Hugging Face Space secrets.

## What This Scaffold Must Not Include

- `.env` or `claire_keys.env`
- Azure credentials
- Google Drive credentials
- private ARE memory
- trace/ledger DBs
- SQLite runtime DBs
- Veritas Legal private matters
- uploaded evidence
- generated FAISS indexes
- raw logs
- model folders

## Initial Run Model

The safest first run should use an external provider configured by secrets, not copied Azure credentials. Local model hosting can be tested later after hardware and storage are approved.

## Approval Gates

Before deploying:

1. Confirm the GitHub branch to clone.
2. Confirm which provider mode to use.
3. Add only approved secrets in Hugging Face settings.
4. Enable persistent storage only after the path plan is accepted.
5. Confirm Veritas Legal private data remains excluded.
