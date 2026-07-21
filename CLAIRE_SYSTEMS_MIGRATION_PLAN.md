# CLAIRE Systems Migration Plan

Mode: plan only. Do not execute until Steve authorizes a specific migration batch.

## Migration Safety Rules
- Preserve full Git history, branches, tags, releases, issues, PRs, Actions, licenses, authorship, provenance, and local-only work.
- Do not rewrite history until secret scanning and legal approval decide it is required.
- Before any transfer, export repo metadata, branch list, tags, releases, issues/PRs where available, Actions secrets names, deploy keys, webhooks, environments, and package/deployment references.
- Treat model files, private legal evidence, memory stores, SQLite databases, `.env`, token files, and logs as non-migratable unless explicitly approved.

## First Ten Safe Migration Actions
1. Authenticate or grant access for `blackstormhorse@gmail.com` private repositories; rerun inventory for that account.
2. Freeze migrations: no transfers/visibility changes until all dirty local checkouts are preserved.
3. Create patch bundles or temporary protected branches for dirty local checkouts: `/home/LuciusPrime/claire`, `/home/LuciusPrime/claire-odyssey`, `/home/LuciusPrime/odyssey-claire-build`, `/home/LuciusPrime/claire_repos/analog--recall-engine`, `/home/LuciusPrime/claire_repos/claire-veritas-legal`.
4. Run full-history secret scan on `clairetech2025-max/claire` and `clairetech2025-max/claire-veritas-legal`.
5. Immediately review `clairetech2025-max/-Claire-Systems-bitbrain-sbc-private` public visibility; plan private transfer to `Claire-Systems/bitbrain` if intentional.
6. Decide ARE/Librarian split: public sanitized `analog-recall-engine` vs private `librarian` implementation.
7. Transfer low-risk documentation repos first only after target naming is approved (`session-capsule-protocol`, org profile/docs).
8. Transfer private commercial repos with full history using GitHub transfer where possible: Spectacle, Sovereign Gateway, Librarian, BitBrain.
9. Transfer or recreate deployment secrets in Claire-Systems environments; never copy secret values into reports or commits.
10. Update README badges, deployment URLs, Hugging Face/Azure references, package names, Docker image names, and Git remotes after transfer validation.

## Product-by-Product Migration Method
### CLAIRE
- Final repo: `Claire-Systems/claire`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire, local: /home/LuciusPrime/claire, local: /home/LuciusPrime/claire-odyssey, local: /home/LuciusPrime/odyssey-claire-build` and dirty local checkouts before action.
- Visibility: PRIVATE DEVELOPMENT initially; split public demo later

### Veritas Legal
- Final repo: `Claire-Systems/veritas-legal`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire-veritas-legal, local: /home/LuciusPrime/claire_repos/claire-veritas-legal, CLAIRE monorepo Veritas routes` and dirty local checkouts before action.
- Visibility: PRIVATE COMMERCIAL until legal/privacy review clears public demo subset

### Analog Recall Engine / ARE
- Final repo: `Claire-Systems/analog-recall-engine`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `Claire-Systems/Analog-Recall-Engine-Legacy, Claire-Systems/analog--recall-engine, clairetech2025-max/claire claire_are/` and dirty local checkouts before action.
- Visibility: PUBLIC OPEN-SOURCE reference only after security/patent review

### Librarian
- Final repo: `Claire-Systems/librarian`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/ARE-Librarian, ARE/cla ire_are variants` and dirty local checkouts before action.
- Visibility: PRIVATE COMMERCIAL

### ARE Spectacle
- Final repo: `Claire-Systems/are-spectacle`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/Claire-Systems-are-spectacle-private, /home/LuciusPrime/claire/private_repo_payloads/are-spectacle-private` and dirty local checkouts before action.
- Visibility: PRIVATE COMMERCIAL

### BitBrain
- Final repo: `Claire-Systems/bitbrain`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/-Claire-Systems-bitbrain-sbc-private, /home/LuciusPrime/claire_repos/bitbrain-sbc, /home/LuciusPrime/claire/private_repo_payloads/bitbrain-sbc-private` and dirty local checkouts before action.
- Visibility: PRIVATE COMMERCIAL

### OfficeAI
- Final repo: `Claire-Systems/officeai`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/OfficeAI-500-Sovereign-Mesh, clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md` and dirty local checkouts before action.
- Visibility: PUBLIC DOCUMENTATION plus PRIVATE COMMERCIAL code if built

### Session Capsule Protocol
- Final repo: `Claire-Systems/session-capsule-protocol`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/session_capsule_protocol, clairetech2025-max/bootstrap_session_capsule_protocol` and dirty local checkouts before action.
- Visibility: PUBLIC DOCUMENTATION or PUBLIC OPEN-SOURCE

### Mobile Android interface
- Final repo: `Claire-Systems/claire-mobile or inside Claire-Systems/claire depending release boundary`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire current claire_gui.py mobile shell, Veritas mobile routes in claire monorepo` and dirty local checkouts before action.
- Visibility: PRIVATE DEVELOPMENT until polished

### Voice interface
- Final repo: `Claire-Systems/claire or Claire-Systems/claire-voice`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire voice/TTS/mic code` and dirty local checkouts before action.
- Visibility: PRIVATE DEVELOPMENT

### Legal evidence ingestion
- Final repo: `Claire-Systems/veritas-legal`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire-veritas-legal, clairetech2025-max/claire Veritas/mobile upload routes` and dirty local checkouts before action.
- Visibility: PRIVATE CUSTOMER / LEGAL DATA for data-bearing branches; public demo only sanitized

### CourtListener integration
- Final repo: `Claire-Systems/veritas-legal`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire-veritas-legal, clairetech2025-max/claire` and dirty local checkouts before action.
- Visibility: PRIVATE COMMERCIAL

### Azure deployment
- Final repo: `Claire-Systems/claire-deployment or private ops folder`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire deployment scripts/nginx/systemd docs` and dirty local checkouts before action.
- Visibility: INTERNAL INFRASTRUCTURE

### Hugging Face deployment
- Final repo: `Claire-Systems/claire-huggingface-deploy or inside claire`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire hf_space and hf_claire_runtime_full` and dirty local checkouts before action.
- Visibility: PRIVATE DEVELOPMENT / PUBLIC DEMONSTRATION after parity

### Shared governance infrastructure
- Final repo: `Claire-Systems/shared-governance or inside claire until stable`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire claire_are, sentinel, diode guard, lane classifier, Claire-Systems/Analog-Recall-Engine-Legacy` and dirty local checkouts before action.
- Visibility: PRIVATE DEVELOPMENT

### DARPA-related prototypes
- Final repo: `Claire-Systems/demos or Claire-Systems/darpa-prototypes-private`
- Method: transfer existing strongest repo if one exists; otherwise import selected history into a new Claire-Systems repo only after preserving local patches.
- Unique code to preserve: inspect candidates `clairetech2025-max/claire demos/docs, APEX--Verifiable-State, session capsule repos` and dirty local checkouts before action.
- Visibility: PRIVATE DEVELOPMENT

## Risks To Flag Before Execution
- Git LFS/model files and large binaries in local or future repos.
- Private legal evidence, uploaded documents, memory stores, traces, SQLite databases, and logs.
- Credentials or infrastructure paths in Git history.
- Broken public links, badges, package names, Docker images, and deployment URLs after transfer.
- GitHub Actions permissions, org secrets, Hugging Face Space links, Azure service configs, Cloudflare/nginx assumptions.
- Divergent local checkouts of the same remote; do not assume GitHub is newest.

## No-Action Confirmation
This file is a migration plan only. No transfer, rename, delete, archive, merge, force-push, history rewrite, remote edit, commit, push, or visibility change was performed.
