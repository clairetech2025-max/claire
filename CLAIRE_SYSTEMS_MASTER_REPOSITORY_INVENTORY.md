# CLAIRE Systems Master Repository Inventory

Mode: audit and migration plan only. No repositories were transferred, renamed, deleted, archived, merged, pushed, or visibility-changed.

## Access Check
- Active GitHub CLI login: `clairetech2025-max`.
- Active GitHub account email from API: `clairetech2025@gmail.com`.
- The CLI is **not** authenticated as `blackstormhorse@gmail.com`.
- Public GitHub owner `Blackstormhorse` is visible and has one public repo: `Blackstormhorse/Fasthorse`.
- To inspect private repos for `blackstormhorse@gmail.com`, Steve should either: run `gh auth login --hostname github.com` and add that account without removing the current one, or grant `clairetech2025-max` / `Claire-Systems` access to the relevant repositories/orgs.

## Totals
- Total GitHub repositories found: 21
- Public repositories: 11
- Private repositories: 10
- Archived repositories: 0
- Local Git checkouts under `/home/LuciusPrime`: 33
- Local-only checkouts with no GitHub remote: 1
- Dirty local checkouts requiring preservation: 5

## Repository Inventory
### Claire-Systems/.github
- URL: https://github.com/Claire-Systems/.github
- Owner: Claire-Systems (Organization)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-06-03T05:49:27Z; size: 1 KB
- Purpose: Organization profile repository.
- Current condition: **DOCUMENTATION ONLY** — Special .github org profile repo.
- Privacy/commercial classification: **PUBLIC DOCUMENTATION**
- Recommended action: **SAFE TO KEEP PUBLIC** — Low executable risk, but docs/positioning should be accurate. Review-level privacy/contact/path findings should be checked.
- Target owner: `Claire-Systems` if retained/active after security review.

### Claire-Systems/Analog-Recall-Engine-Legacy
- URL: https://github.com/Claire-Systems/Analog-Recall-Engine-Legacy
- Owner: Claire-Systems (Organization)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-06-02T19:15:50Z; size: 37 KB
- Purpose: Legacy public Analog Recall Engine implementation/reference.
- Current condition: **LEGACY** — ARE naming and Python implementation, likely predecessor to current claire_are package.
- Privacy/commercial classification: **LEGACY PUBLIC**
- Recommended action: **NEEDS SECURITY REVIEW** — Likely predecessor/duplicate; preserve until replacement map is finalized. Review-level privacy/contact/path findings should be checked.
- Target owner: `Claire-Systems` if retained/active after security review.

### Claire-Systems/analog--recall-engine
- URL: https://github.com/Claire-Systems/analog--recall-engine
- Owner: Claire-Systems (Organization)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-06-02T19:14:45Z; size: 4 KB
- Purpose: Documentation or profile repository with little/no executable code.
- Current condition: **DOCUMENTATION ONLY** — README/profile content only or nearly only.
- Privacy/commercial classification: **PUBLIC DOCUMENTATION**
- Recommended action: **NEEDS SECURITY REVIEW** — Low executable risk, but docs/positioning should be accurate. Review-level privacy/contact/path findings should be checked.
- Target owner: `Claire-Systems` if retained/active after security review.

### Claire-Systems/claire-code-coach-level-1
- URL: https://github.com/Claire-Systems/claire-code-coach-level-1
- Owner: Claire-Systems (Organization)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: main; last push: 2026-05-21T13:48:30Z; size: 44 KB
- Purpose: Code Coach training/prototype repository.
- Current condition: **PROTOTYPE** — Training app naming and small code/docs tree.
- Privacy/commercial classification: **PRIVATE COMMERCIAL**
- Recommended action: **NEEDS SECURITY REVIEW** — Review-level credential/privacy patterns found; keep private until manually cleared.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/-Claire-Systems-bitbrain-sbc-private
- URL: https://github.com/clairetech2025-max/-Claire-Systems-bitbrain-sbc-private
- Owner: clairetech2025-max (Personal account)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-06-02T19:33:44Z; size: 10 KB
- Purpose: BitBrain SBC private/commercial code package or hardware-oriented prototype.
- Current condition: **SECURITY REVIEW REQUIRED** — Name says private; visibility must be checked against GitHub metadata.
- Privacy/commercial classification: **PRIVATE COMMERCIAL**
- Recommended action: **MAKE PRIVATE** — Repository name says private while GitHub visibility is public; verify intent and make private unless it is deliberately sanitized.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/AI-Audit-Copilot
- URL: https://github.com/clairetech2025-max/AI-Audit-Copilot
- Owner: clairetech2025-max (Personal account)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: main; last push: 2026-05-03T06:58:58Z; size: 3 KB
- Purpose: AI audit/copilot prototype or placeholder.
- Current condition: **EMPTY** — Small/private repo; limited code evidence.
- Privacy/commercial classification: **ARCHIVE CANDIDATE**
- Recommended action: **NEEDS README** — Low executable risk, but docs/positioning should be accurate.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/AI-Audit-Copilot-
- URL: https://github.com/clairetech2025-max/AI-Audit-Copilot-
- Owner: clairetech2025-max (Personal account)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: ; last push: 2026-05-02T23:24:28Z; size: 0 KB
- Purpose: Empty placeholder repository.
- Current condition: **EMPTY** — Repository clone contains no working files beyond git metadata.
- Privacy/commercial classification: **ARCHIVE CANDIDATE**
- Recommended action: **NEEDS README** — Low executable risk, but docs/positioning should be accurate.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/APEX--Verifiable-State
- URL: https://github.com/clairetech2025-max/APEX--Verifiable-State
- Owner: clairetech2025-max (Personal account)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: main; last push: 2026-05-03T21:51:47Z; size: 20 KB
- Purpose: APEX/verifiable state or signal intelligence prototype.
- Current condition: **PROTOTYPE** — Prototype naming and small Python codebase.
- Privacy/commercial classification: **PRIVATE COMMERCIAL**
- Recommended action: **NEEDS CLEANUP** — Prototype/partial state; review documentation, tests, and sensitive data before broader exposure.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/ARE
- URL: https://github.com/clairetech2025-max/ARE
- Owner: clairetech2025-max (Personal account)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: ; last push: 2026-02-23T19:05:38Z; size: 0 KB
- Purpose: Empty placeholder repository.
- Current condition: **EMPTY** — Repository clone contains no working files beyond git metadata.
- Privacy/commercial classification: **ARCHIVE CANDIDATE**
- Recommended action: **NEEDS README** — Low executable risk, but docs/positioning should be accurate.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/ARE-Librarian
- URL: https://github.com/clairetech2025-max/ARE-Librarian
- Owner: clairetech2025-max (Personal account)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: main; last push: 2026-06-04T08:29:03Z; size: 8 KB
- Purpose: Documentation or profile repository with little/no executable code.
- Current condition: **DOCUMENTATION ONLY** — README/profile content only or nearly only.
- Privacy/commercial classification: **PRIVATE COMMERCIAL**
- Recommended action: **NEEDS SECURITY REVIEW** — Review-level credential/privacy patterns found; keep private until manually cleared.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/Claire-Systems-apex-signal-intelligence-private
- URL: https://github.com/clairetech2025-max/Claire-Systems-apex-signal-intelligence-private
- Owner: clairetech2025-max (Personal account)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: ; last push: 2026-05-01T20:48:21Z; size: 0 KB
- Purpose: Empty placeholder repository.
- Current condition: **EMPTY** — Repository clone contains no working files beyond git metadata.
- Privacy/commercial classification: **PRIVATE COMMERCIAL**
- Recommended action: **NEEDS README** — Low executable risk, but docs/positioning should be accurate.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/Claire-Systems-are-spectacle-private
- URL: https://github.com/clairetech2025-max/Claire-Systems-are-spectacle-private
- Owner: clairetech2025-max (Personal account)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: main; last push: 2026-05-02T08:57:39Z; size: 27 KB
- Purpose: Private ARE Spectacle commercial/demo package around governed memory.
- Current condition: **COMMERCIAL / PRIVATE** — Private repo with Python package payload and commercial naming.
- Privacy/commercial classification: **PRIVATE COMMERCIAL**
- Recommended action: **NEEDS SECURITY REVIEW** — Review-level credential/privacy patterns found; keep private until manually cleared.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private
- URL: https://github.com/clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private
- Owner: clairetech2025-max (Personal account)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: main; last push: 2026-05-02T08:57:41Z; size: 7 KB
- Purpose: Private sovereign execution gateway prototype/package.
- Current condition: **COMMERCIAL / PRIVATE** — Private repo with execution-gateway naming.
- Privacy/commercial classification: **PRIVATE COMMERCIAL**
- Recommended action: **KEEP PRIVATE** — Commercial/proprietary product or private package naming.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/OfficeAI-500-Sovereign-Mesh
- URL: https://github.com/clairetech2025-max/OfficeAI-500-Sovereign-Mesh
- Owner: clairetech2025-max (Personal account)
- Visibility: PRIVATE; archived: False; fork: False
- Default branch: ; last push: 2026-05-02T22:11:36Z; size: 0 KB
- Purpose: Empty placeholder repository.
- Current condition: **EMPTY** — Repository clone contains no working files beyond git metadata.
- Privacy/commercial classification: **ARCHIVE CANDIDATE**
- Recommended action: **NEEDS README** — Low executable risk, but docs/positioning should be accurate.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md
- URL: https://github.com/clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md
- Owner: clairetech2025-max (Personal account)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-06-02T19:36:08Z; size: 4 KB
- Purpose: Documentation or profile repository with little/no executable code.
- Current condition: **DOCUMENTATION ONLY** — README/profile content only or nearly only.
- Privacy/commercial classification: **PUBLIC DOCUMENTATION**
- Recommended action: **SAFE TO KEEP PUBLIC** — Low executable risk, but docs/positioning should be accurate. Review-level privacy/contact/path findings should be checked.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/bootstrap_session_capsule_protocol
- URL: https://github.com/clairetech2025-max/bootstrap_session_capsule_protocol
- Owner: clairetech2025-max (Personal account)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-05-20T13:53:21Z; size: 3 KB
- Purpose: Documentation or profile repository with little/no executable code.
- Current condition: **DOCUMENTATION ONLY** — README/profile content only or nearly only.
- Privacy/commercial classification: **PUBLIC DOCUMENTATION**
- Recommended action: **SAFE TO KEEP PUBLIC** — Low executable risk, but docs/positioning should be accurate.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/claire
- URL: https://github.com/clairetech2025-max/claire
- Owner: clairetech2025-max (Personal account)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-07-12T18:28:26Z; size: 3183 KB
- Purpose: Primary CLAIRE monorepo: public GUI/runtime, ARE package, Veritas integrations, Venture subsystem, demos, deployment scripts, and many legacy/prototype components.
- Current condition: **PARTIAL** — Large active monorepo with working live services but dirty worktree, many prototypes, and security review findings.
- Privacy/commercial classification: **PRIVATE COMMERCIAL**
- Recommended action: **NEEDS SECURITY REVIEW** — Main product repository contains infrastructure paths, public contact details, runtime/deployment code, and possible sensitive history; review before deciding public/private.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/claire-code-coach-level-1.
- URL: https://github.com/clairetech2025-max/claire-code-coach-level-1.
- Owner: clairetech2025-max (Personal account)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-05-21T00:39:00Z; size: 2 KB
- Purpose: Documentation or profile repository with little/no executable code.
- Current condition: **DOCUMENTATION ONLY** — README/profile content only or nearly only.
- Privacy/commercial classification: **PUBLIC DOCUMENTATION**
- Recommended action: **SAFE TO KEEP PUBLIC** — Low executable risk, but docs/positioning should be accurate.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/claire-veritas-legal
- URL: https://github.com/clairetech2025-max/claire-veritas-legal
- Owner: clairetech2025-max (Personal account)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-07-13T08:22:32Z; size: 310 KB
- Purpose: Standalone Veritas Legal workstation for matter/evidence workflow, CourtListener and EDGAR-backed legal research, firm authority, and document production.
- Current condition: **MOSTLY WORKING** — FastAPI web app, tests, live service evidence, CourtListener/EDGAR code present.
- Privacy/commercial classification: **PRIVATE CUSTOMER / LEGAL DATA**
- Recommended action: **NEEDS SECURITY REVIEW** — Main product repository contains infrastructure paths, public contact details, runtime/deployment code, and possible sensitive history; review before deciding public/private.
- Target owner: `Claire-Systems` if retained/active after security review.

### clairetech2025-max/session_capsule_protocol
- URL: https://github.com/clairetech2025-max/session_capsule_protocol
- Owner: clairetech2025-max (Personal account)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: main; last push: 2026-06-03T14:15:17Z; size: 9 KB
- Purpose: Documentation or profile repository with little/no executable code.
- Current condition: **DOCUMENTATION ONLY** — README/profile content only or nearly only.
- Privacy/commercial classification: **PUBLIC DOCUMENTATION**
- Recommended action: **SAFE TO KEEP PUBLIC** — Low executable risk, but docs/positioning should be accurate.
- Target owner: `Claire-Systems` if retained/active after security review.

### Blackstormhorse/Fasthorse
- URL: https://github.com/Blackstormhorse/Fasthorse
- Owner: Blackstormhorse (Personal account)
- Visibility: PUBLIC; archived: False; fork: False
- Default branch: ; last push: 2023-01-05T01:07:00Z; size: 0 KB
- Purpose: Empty public repository visible under Blackstormhorse. No executable content found in shallow clone.
- Current condition: **EMPTY** — GitHub reports zero disk usage/default branch blank; clone warned empty repository.
- Privacy/commercial classification: **ARCHIVE CANDIDATE**
- Recommended action: **NEEDS README** — Empty public personal-account repo; decide whether it has any CLAIRE purpose before transfer/archive.
- Target owner: `Claire-Systems` if retained/active after security review.

## Local Checkouts
### /home/LuciusPrime/.codex/.tmp/plugins
- Remote: `none`
- GitHub owner/name: `none`
- Current branch: `master`; upstream: `none`; ahead/behind: `n/a`
- Latest commit: `11c74d6ba24d3a6d48f54a194cd00ef3beea18f9 2026-07-13T15:38:40-04:00 Add ClickUp website URL (#384)`
- Dirty status: `False`
- Remote accessible in current audit: `False`
- Tags: `none`

### /home/LuciusPrime/claire
- Remote: `origin	https://github.com/clairetech2025-max/claire.git (fetch)
origin	https://github.com/clairetech2025-max/claire.git (push)`
- GitHub owner/name: `clairetech2025-max/claire`
- Current branch: `codex/venture-intelligence-slice-1`; upstream: `origin/codex/venture-intelligence-slice-1`; ahead/behind: `0	0`
- Latest commit: `67b8cf1eb4b5e9ceb800bc5799a467fedc5a46c1 2026-07-12T18:22:31+00:00 Document Veritas archaeology baseline`
- Dirty status: `True`
- Remote accessible in current audit: `True`
- Tags: `blue-veritas-pre-mobile-20260712T101453Z, blue-veritas-pre-route-20260712T182324Z`

### /home/LuciusPrime/claire-odyssey
- Remote: `origin	https://github.com/clairetech2025-max/claire.git (fetch)
origin	https://github.com/clairetech2025-max/claire.git (push)`
- GitHub owner/name: `clairetech2025-max/claire`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `37bfcea4a39da33f6bd00d080453207f2e965a4d 2026-05-24T07:56:35-07:00 Create Claire's Odyssey`
- Dirty status: `True`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/Claire-Systems__.github
- Remote: `origin	https://github.com/Claire-Systems/.github.git (fetch)
origin	https://github.com/Claire-Systems/.github.git (push)`
- GitHub owner/name: `Claire-Systems/.github`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `06392738fb9537f5ee4550c18b51fb32fac4b8ea 2026-06-03T05:49:15+00:00 Add Claire Systems organization profile`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/Claire-Systems__Analog-Recall-Engine-Legacy
- Remote: `origin	https://github.com/Claire-Systems/Analog-Recall-Engine-Legacy.git (fetch)
origin	https://github.com/Claire-Systems/Analog-Recall-Engine-Legacy.git (push)`
- GitHub owner/name: `Claire-Systems/Analog-Recall-Engine-Legacy`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `5a6cffb69d7bae363aa7e422b2d1bca90ff37bb6 2026-06-02T12:15:50-07:00 Professional README for ARE Spectacle v2 - Commercial governance version`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/Claire-Systems__analog--recall-engine
- Remote: `origin	https://github.com/Claire-Systems/analog--recall-engine.git (fetch)
origin	https://github.com/Claire-Systems/analog--recall-engine.git (push)`
- GitHub owner/name: `Claire-Systems/analog--recall-engine`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `4bbcf4b8730f46f356fe97ac6c513933675efb29 2026-06-02T12:14:45-07:00 Add Proprietary License for ARE`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/Claire-Systems__claire-code-coach-level-1
- Remote: `origin	https://github.com/Claire-Systems/claire-code-coach-level-1.git (fetch)
origin	https://github.com/Claire-Systems/claire-code-coach-level-1.git (push)`
- GitHub owner/name: `Claire-Systems/claire-code-coach-level-1`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `2df4fa10be4fabb46d2b74a067f64af910212e5f 2026-05-21T06:41:37-07:00 Add buyer launcher for Python PyGym`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__-Claire-Systems-bitbrain-sbc-private
- Remote: `origin	https://github.com/clairetech2025-max/-Claire-Systems-bitbrain-sbc-private.git (fetch)
origin	https://github.com/clairetech2025-max/-Claire-Systems-bitbrain-sbc-private.git (push)`
- GitHub owner/name: `clairetech2025-max/-Claire-Systems-bitbrain-sbc-private`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `2ca06134231ef8cb91954c1d34ea68f805997e39 2026-06-02T12:33:44-07:00 Add Proprietary License for BitBrain SBC`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__AI-Audit-Copilot
- Remote: `origin	https://github.com/clairetech2025-max/AI-Audit-Copilot.git (fetch)
origin	https://github.com/clairetech2025-max/AI-Audit-Copilot.git (push)`
- GitHub owner/name: `clairetech2025-max/AI-Audit-Copilot`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `8c907ae0d13263aa20f7633593969fd7f9f5ef13 2026-05-02T23:58:58-07:00 Add GitHub Actions workflow for building Python app`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__AI-Audit-Copilot-
- Remote: `origin	https://github.com/clairetech2025-max/AI-Audit-Copilot-.git (fetch)
origin	https://github.com/clairetech2025-max/AI-Audit-Copilot-.git (push)`
- GitHub owner/name: `clairetech2025-max/AI-Audit-Copilot-`
- Current branch: `HEAD`; upstream: `@{u}`; ahead/behind: `n/a`
- Latest commit: ``
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__APEX--Verifiable-State
- Remote: `origin	https://github.com/clairetech2025-max/APEX--Verifiable-State.git (fetch)
origin	https://github.com/clairetech2025-max/APEX--Verifiable-State.git (push)`
- GitHub owner/name: `clairetech2025-max/APEX--Verifiable-State`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `a67c484315b9b512997f1362f04f197add2f75bd 2026-05-03T14:51:47-07:00 Add comprehensive unit tests for APEX engine`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__ARE
- Remote: `origin	https://github.com/clairetech2025-max/ARE.git (fetch)
origin	https://github.com/clairetech2025-max/ARE.git (push)`
- GitHub owner/name: `clairetech2025-max/ARE`
- Current branch: `HEAD`; upstream: `@{u}`; ahead/behind: `n/a`
- Latest commit: ``
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__ARE-Librarian
- Remote: `origin	https://github.com/clairetech2025-max/ARE-Librarian.git (fetch)
origin	https://github.com/clairetech2025-max/ARE-Librarian.git (push)`
- GitHub owner/name: `clairetech2025-max/ARE-Librarian`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `e8231aa60600563a253817cc631eb15d860e6cde 2026-06-04T01:29:03-07:00 Rename source code to src/are_sidecar.py`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__Claire-Systems-apex-signal-intelligence-private
- Remote: `origin	https://github.com/clairetech2025-max/Claire-Systems-apex-signal-intelligence-private.git (fetch)
origin	https://github.com/clairetech2025-max/Claire-Systems-apex-signal-intelligence-private.git (push)`
- GitHub owner/name: `clairetech2025-max/Claire-Systems-apex-signal-intelligence-private`
- Current branch: `HEAD`; upstream: `@{u}`; ahead/behind: `n/a`
- Latest commit: ``
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__Claire-Systems-are-spectacle-private
- Remote: `origin	https://github.com/clairetech2025-max/Claire-Systems-are-spectacle-private.git (fetch)
origin	https://github.com/clairetech2025-max/Claire-Systems-are-spectacle-private.git (push)`
- GitHub owner/name: `clairetech2025-max/Claire-Systems-are-spectacle-private`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `e26635b967a5f1725d3e7409b815b5cc68b01bae 2026-05-01T16:56:29-07:00 Delete .github/workflows/build.yml`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__Claire-Systems-sovereign-execution-gateway-private
- Remote: `origin	https://github.com/clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private.git (fetch)
origin	https://github.com/clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private.git (push)`
- GitHub owner/name: `clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `6c94b5050d69572a9a5124e5ae5b573ea86a2319 2026-05-01T01:15:20+00:00 initial private Sovereign Execution Gateway Gumroad release`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__OfficeAI-500-Sovereign-Mesh
- Remote: `origin	https://github.com/clairetech2025-max/OfficeAI-500-Sovereign-Mesh.git (fetch)
origin	https://github.com/clairetech2025-max/OfficeAI-500-Sovereign-Mesh.git (push)`
- GitHub owner/name: `clairetech2025-max/OfficeAI-500-Sovereign-Mesh`
- Current branch: `HEAD`; upstream: `@{u}`; ahead/behind: `n/a`
- Latest commit: ``
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__OfficeAI-500-Sovereign-Mesh-README.md
- Remote: `origin	https://github.com/clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md.git (fetch)
origin	https://github.com/clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md.git (push)`
- GitHub owner/name: `clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `376e194014ef6d98a63a9eaa369996afcb6bfdf1 2026-06-02T12:36:08-07:00 Add Proprietary License for OfficeAI 500`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__bootstrap_session_capsule_protocol
- Remote: `origin	https://github.com/clairetech2025-max/bootstrap_session_capsule_protocol.git (fetch)
origin	https://github.com/clairetech2025-max/bootstrap_session_capsule_protocol.git (push)`
- GitHub owner/name: `clairetech2025-max/bootstrap_session_capsule_protocol`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `a4ccd49b4aa0ddb94cec2af3dc7107d54c265bdf 2026-05-20T06:53:20-07:00 Revise README for CLAIRE Session Capsule Protocol`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__claire
- Remote: `origin	https://github.com/clairetech2025-max/claire.git (fetch)
origin	https://github.com/clairetech2025-max/claire.git (push)`
- GitHub owner/name: `clairetech2025-max/claire`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `c210ecff7026d83a0f518a62443a6891ac2a0ef3 2026-06-02T12:43:58-07:00 Claire Systems Market Analysis Report - Technology Stack Valuation`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__claire-code-coach-level-1.
- Remote: `origin	https://github.com/clairetech2025-max/claire-code-coach-level-1..git (fetch)
origin	https://github.com/clairetech2025-max/claire-code-coach-level-1..git (push)`
- GitHub owner/name: `clairetech2025-max/claire-code-coach-level-1.`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `96a8d3c6429ffa0514ed3be25a9b29b4edb5c509 2026-05-20T17:38:59-07:00 Create README for CLAIRE Code Coach`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__claire-veritas-legal
- Remote: `origin	https://github.com/clairetech2025-max/claire-veritas-legal.git (fetch)
origin	https://github.com/clairetech2025-max/claire-veritas-legal.git (push)`
- GitHub owner/name: `clairetech2025-max/claire-veritas-legal`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `a456c7e4320898387cdc33ddcce56d9ffdf89e8d 2026-06-17T19:21:18+00:00 Fix Veritas Legal AI bridge and grounded search`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__session_capsule_protocol
- Remote: `origin	https://github.com/clairetech2025-max/session_capsule_protocol.git (fetch)
origin	https://github.com/clairetech2025-max/session_capsule_protocol.git (push)`
- GitHub owner/name: `clairetech2025-max/session_capsule_protocol`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `bb6247585a4b2de7ff558b3012eff02f35ed26da 2026-06-03T07:15:17-07:00 Create  Session Capsule Protocol proof artifacts`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire/llama.cpp
- Remote: `origin	https://github.com/ggerganov/llama.cpp (fetch)
origin	https://github.com/ggerganov/llama.cpp (push)`
- GitHub owner/name: `ggerganov/llama.cpp`
- Current branch: `master`; upstream: `origin/master`; ahead/behind: `0	0`
- Latest commit: `b572d1ecd62210229e04cdeffd3ae80dd59f0921 2026-04-16T13:13:11+03:00 codeowners: add team member comments (#21714)`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `b1046, b1047, b1048, b1049, b1050, b1052, b1054, b1056, b1057, b1059, b1060, b1063`

### /home/LuciusPrime/claire/private_repo_payloads/are-spectacle-private
- Remote: `origin	git@github.com:clairetech2025-max/Claire-Systems-are-spectacle-private.git (fetch)
origin	git@github.com:clairetech2025-max/Claire-Systems-are-spectacle-private.git (push)`
- GitHub owner/name: `clairetech2025-max/Claire-Systems-are-spectacle-private`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `83ee7584f480612f9874db0d515ce8965421486f 2026-05-01T01:08:46+00:00 initial private ARE Spectacle Gumroad release`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `v2026.05.02.0857`

### /home/LuciusPrime/claire/private_repo_payloads/bitbrain-sbc-private
- Remote: `origin	git@github.com:clairetech2025-max/-Claire-Systems-bitbrain-sbc-private.git (fetch)
origin	git@github.com:clairetech2025-max/-Claire-Systems-bitbrain-sbc-private.git (push)`
- GitHub owner/name: `clairetech2025-max/-Claire-Systems-bitbrain-sbc-private`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `af63fac7aad41528f9797b7de634b13bd62d2a82 2026-05-01T01:19:22+00:00 initial private BitBrain SBC Gumroad release`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `v2026.05.02.0857`

### /home/LuciusPrime/claire/private_repo_payloads/sovereign-execution-gateway-private
- Remote: `origin	git@github.com:clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private.git (fetch)
origin	git@github.com:clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private.git (push)`
- GitHub owner/name: `clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `6c94b5050d69572a9a5124e5ae5b573ea86a2319 2026-05-01T01:15:20+00:00 initial private Sovereign Execution Gateway Gumroad release`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `v2026.05.02.0857`

### /home/LuciusPrime/claire_public_releases/veritas_legal_evidence_engine
- Remote: `none`
- GitHub owner/name: `none`
- Current branch: `main`; upstream: `none`; ahead/behind: `n/a`
- Latest commit: `ecaa27110520e6b898537c372670daa882ebc7eb 2026-07-05T12:02:57+00:00 Document Original ARE legal contract`
- Dirty status: `False`
- Remote accessible in current audit: `False`
- Tags: `none`

### /home/LuciusPrime/claire_repos/.github
- Remote: `origin	https://github.com/Claire-Systems/.github.git (fetch)
origin	https://github.com/Claire-Systems/.github.git (push)`
- GitHub owner/name: `Claire-Systems/.github`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `06392738fb9537f5ee4550c18b51fb32fac4b8ea 2026-06-03T05:49:15+00:00 Add Claire Systems organization profile`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire_repos/analog--recall-engine
- Remote: `origin	https://github.com/Claire-Systems/analog--recall-engine.git (fetch)
origin	https://github.com/Claire-Systems/analog--recall-engine.git (push)`
- GitHub owner/name: `Claire-Systems/analog--recall-engine`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `4bbcf4b8730f46f356fe97ac6c513933675efb29 2026-06-02T12:14:45-07:00 Add Proprietary License for ARE`
- Dirty status: `True`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/claire_repos/bitbrain-sbc
- Remote: `origin	https://github.com/clairetech2025-max/-Claire-Systems-bitbrain-sbc-private.git (fetch)
origin	https://github.com/clairetech2025-max/-Claire-Systems-bitbrain-sbc-private.git (push)`
- GitHub owner/name: `clairetech2025-max/-Claire-Systems-bitbrain-sbc-private`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `2ca06134231ef8cb91954c1d34ea68f805997e39 2026-06-02T12:33:44-07:00 Add Proprietary License for BitBrain SBC`
- Dirty status: `False`
- Remote accessible in current audit: `True`
- Tags: `v2026.05.02.0857`

### /home/LuciusPrime/claire_repos/claire-veritas-legal
- Remote: `origin	https://github.com/clairetech2025-max/claire-veritas-legal.git (fetch)
origin	https://github.com/clairetech2025-max/claire-veritas-legal.git (push)`
- GitHub owner/name: `clairetech2025-max/claire-veritas-legal`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `070330ac10da5b6196ac36c7d05318753dc1de38 2026-07-13T08:22:26+00:00 Bring CourtListener and SEC EDGAR online`
- Dirty status: `True`
- Remote accessible in current audit: `True`
- Tags: `none`

### /home/LuciusPrime/odyssey-claire-build
- Remote: `origin	https://github.com/clairetech2025-max/claire.git (fetch)
origin	https://github.com/clairetech2025-max/claire.git (push)`
- GitHub owner/name: `clairetech2025-max/claire`
- Current branch: `main`; upstream: `origin/main`; ahead/behind: `0	0`
- Latest commit: `37bfcea4a39da33f6bd00d080453207f2e965a4d 2026-05-24T07:56:35-07:00 Create Claire's Odyssey`
- Dirty status: `True`
- Remote accessible in current audit: `True`
- Tags: `none`

