# GitHub Publication Security Audit

Generated: 2026-07-12T00:48:22.283607Z

No secret values are printed in this report. `gitleaks` was not installed on this VM, so this pass used local clones, regex scanning of current text files, sensitive filename detection, and `git rev-list --objects --all` path inspection. Any repository with flags is not approved for new publication.

| Repository | Visibility | Security result | Flags without values | Limitations |
| --- | --- | --- | --- | --- |
| clairetech2025-max/claire | PUBLIC | PUBLIC_REVIEW_REQUIRED | history path: `.env.example`<br>history path: `claire_state/claire_memory.db`<br>history path: `claire_state/claire_runtime_traces.db`<br>history path: `hf_claire_runtime_full/.env.example`<br>history path: `hf_space/.env.example`<br>internal_local_url: `ARE_SERVER_LOCKED.py`, `LAUNCH.sh`, `claire_are_loader.py`, `claire_bootstrap.sh`, `claire_courtlistener.py`, `claire_gui.py`<br>email_address: `MARKET_ANALYSIS_REPORT.md`, `claire_gui.py`, `gumroad_builds/ARE-Spectacle/push_after_private_repo_created.sh`, `gumroad_builds/BitBrain-SBC/push_after_private_repo_created.sh`, `gumroad_builds/CREATE_PRIVATE_REPOS.md`, `gumroad_builds/Sovereign-Execution-Gateway/push_after_private_repo_created.sh`<br>azure_connection_string: `claire_azure_sync.py`<br>generic_api_key_assignment: `claire_courtlistener.py`, `claire_gui.py`, `claire_scholar.py`<br>phone_like: `claire_gui.py` | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/claire-veritas-legal | PUBLIC | PUBLIC_REVIEW_REQUIRED | sensitive filename: `.env.example`<br>history path: `.env.example`<br>internal_local_url: `README.md`, `SELLABLE_PACKAGE.md`, `SESSION.md`, `smoke_test.py`, `web/services/llm.py`<br>generic_api_key_assignment: `web/app.py`, `web/services/courtlistener.py` | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/ARE-Librarian | PRIVATE | BLOCKED | generic_api_key_assignment: `src/are_sidecar.py`<br>internal_local_url: `src/are_sidecar.py` | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/session_capsule_protocol | PUBLIC | NO_AUTOMATED_FLAGS | none | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md | PUBLIC | PUBLIC_REVIEW_REQUIRED | email_address: `README.md` | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/-Claire-Systems-bitbrain-sbc-private | PUBLIC | PUBLIC_REVIEW_REQUIRED | email_address: `README.md`<br>internal_local_url: `README_START_HERE.txt`, `app/main.py`, `sample_requests.json` | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/claire-code-coach-level-1. | PUBLIC | NO_AUTOMATED_FLAGS | none | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/bootstrap_session_capsule_protocol | PUBLIC | NO_AUTOMATED_FLAGS | none | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/APEX--Verifiable-State | PRIVATE | NO_AUTOMATED_FLAGS | none | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/AI-Audit-Copilot | PRIVATE | NO_AUTOMATED_FLAGS | none | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/AI-Audit-Copilot- | PRIVATE | NO_AUTOMATED_FLAGS | none | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/OfficeAI-500-Sovereign-Mesh | PRIVATE | NO_AUTOMATED_FLAGS | none | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private | PRIVATE | BLOCKED | internal_local_url: `README.md`, `README_START_HERE.txt`, `app/main.py`, `sample_requests.json` | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/Claire-Systems-are-spectacle-private | PRIVATE | BLOCKED | internal_local_url: `DEPLOYMENT.md`, `README_START_HERE.txt`, `sample_requests.json` | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/Claire-Systems-apex-signal-intelligence-private | PRIVATE | NO_AUTOMATED_FLAGS | none | gitleaks unavailable; regex/current-tree/history-path scan only |
| clairetech2025-max/ARE | PRIVATE | NO_AUTOMATED_FLAGS | none | gitleaks unavailable; regex/current-tree/history-path scan only |
| Claire-Systems/.github | PUBLIC | PUBLIC_REVIEW_REQUIRED | email_address: `profile/README.md` | gitleaks unavailable; regex/current-tree/history-path scan only |
| Claire-Systems/Analog-Recall-Engine-Legacy | PUBLIC | PUBLIC_REVIEW_REQUIRED | email_address: `README.md` | gitleaks unavailable; regex/current-tree/history-path scan only |
| Claire-Systems/analog--recall-engine | PUBLIC | PUBLIC_REVIEW_REQUIRED | email_address: `README.md` | gitleaks unavailable; regex/current-tree/history-path scan only |
| Claire-Systems/claire-code-coach-level-1 | PRIVATE | BLOCKED | internal_local_url: `README.md`, `claire_ai.py`<br>generic_api_key_assignment: `claire_ai.py` | gitleaks unavailable; regex/current-tree/history-path scan only |
