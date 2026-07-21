# CLAIRE Systems Target Structure

Proposed final organization: `Claire-Systems`. This is a plan only; no repositories were transferred or changed.

```text
Claire-Systems
├── claire  # canonical core runtime; private until public surface cleaned
├── veritas-legal  # standalone Veritas Legal product; private commercial/customer data boundary
├── analog-recall-engine  # sanitized public reference ARE package; not private Librarian internals
├── librarian  # private commercial memory/recall implementation if distinct from ARE
├── are-spectacle  # private/commercial demo/product package
├── bitbrain  # private commercial SBC/product repo
├── officeai  # docs plus eventual private product code if needed
├── session-capsule-protocol  # public protocol/docs repo
├── claire-mobile  # only if mobile UI separates from core; otherwise keep in claire
├── claire-voice  # only if voice runtime separates from core; otherwise keep in claire
├── shared-governance  # only after APIs stabilize; otherwise keep in claire
├── demos  # sanitized public demos only
├── legacy  # not a repo; use archived/legacy labels/topics or `legacy-*` repo names
```

## Authoritative Repository Decisions
### CLAIRE
- Candidate repositories: clairetech2025-max/claire, local: /home/LuciusPrime/claire, local: /home/LuciusPrime/claire-odyssey, local: /home/LuciusPrime/odyssey-claire-build
- Strongest candidate: clairetech2025-max/claire plus current live local branch /home/LuciusPrime/claire
- Recommended final repository name: `Claire-Systems/claire`
- Recommended visibility: **PRIVATE DEVELOPMENT initially; split public demo later**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Veritas Legal
- Candidate repositories: clairetech2025-max/claire-veritas-legal, local: /home/LuciusPrime/claire_repos/claire-veritas-legal, CLAIRE monorepo Veritas routes
- Strongest candidate: clairetech2025-max/claire-veritas-legal for standalone product; preserve CLAIRE route integrations separately
- Recommended final repository name: `Claire-Systems/veritas-legal`
- Recommended visibility: **PRIVATE COMMERCIAL until legal/privacy review clears public demo subset**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Analog Recall Engine / ARE
- Candidate repositories: Claire-Systems/Analog-Recall-Engine-Legacy, Claire-Systems/analog--recall-engine, clairetech2025-max/claire claire_are/
- Strongest candidate: clairetech2025-max/claire claire_are/ for active implementation; Claire-Systems/Analog-Recall-Engine-Legacy as public legacy reference
- Recommended final repository name: `Claire-Systems/analog-recall-engine`
- Recommended visibility: **PUBLIC OPEN-SOURCE reference only after security/patent review**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Librarian
- Candidate repositories: clairetech2025-max/ARE-Librarian, ARE/cla ire_are variants
- Strongest candidate: clairetech2025-max/ARE-Librarian, but current scan found very small/doc-like tree and needs manual source review
- Recommended final repository name: `Claire-Systems/librarian`
- Recommended visibility: **PRIVATE COMMERCIAL**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### ARE Spectacle
- Candidate repositories: clairetech2025-max/Claire-Systems-are-spectacle-private, /home/LuciusPrime/claire/private_repo_payloads/are-spectacle-private
- Strongest candidate: clairetech2025-max/Claire-Systems-are-spectacle-private
- Recommended final repository name: `Claire-Systems/are-spectacle`
- Recommended visibility: **PRIVATE COMMERCIAL**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### BitBrain
- Candidate repositories: clairetech2025-max/-Claire-Systems-bitbrain-sbc-private, /home/LuciusPrime/claire_repos/bitbrain-sbc, /home/LuciusPrime/claire/private_repo_payloads/bitbrain-sbc-private
- Strongest candidate: same GitHub repo plus local payload; current public visibility conflicts with private name
- Recommended final repository name: `Claire-Systems/bitbrain`
- Recommended visibility: **PRIVATE COMMERCIAL**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### OfficeAI
- Candidate repositories: clairetech2025-max/OfficeAI-500-Sovereign-Mesh, clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md
- Strongest candidate: README repo for public docs; private empty repo for future code
- Recommended final repository name: `Claire-Systems/officeai`
- Recommended visibility: **PUBLIC DOCUMENTATION plus PRIVATE COMMERCIAL code if built**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Session Capsule Protocol
- Candidate repositories: clairetech2025-max/session_capsule_protocol, clairetech2025-max/bootstrap_session_capsule_protocol
- Strongest candidate: session_capsule_protocol as canonical docs/protocol; bootstrap as starter/legacy
- Recommended final repository name: `Claire-Systems/session-capsule-protocol`
- Recommended visibility: **PUBLIC DOCUMENTATION or PUBLIC OPEN-SOURCE**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Mobile Android interface
- Candidate repositories: clairetech2025-max/claire current claire_gui.py mobile shell, Veritas mobile routes in claire monorepo
- Strongest candidate: current /home/LuciusPrime/claire branch contains latest mobile-first CLAIRE UI work
- Recommended final repository name: `Claire-Systems/claire-mobile or inside Claire-Systems/claire depending release boundary`
- Recommended visibility: **PRIVATE DEVELOPMENT until polished**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Voice interface
- Candidate repositories: clairetech2025-max/claire voice/TTS/mic code
- Strongest candidate: claire monorepo
- Recommended final repository name: `Claire-Systems/claire or Claire-Systems/claire-voice`
- Recommended visibility: **PRIVATE DEVELOPMENT**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Legal evidence ingestion
- Candidate repositories: clairetech2025-max/claire-veritas-legal, clairetech2025-max/claire Veritas/mobile upload routes
- Strongest candidate: claire-veritas-legal standalone plus CLAIRE integration adapters
- Recommended final repository name: `Claire-Systems/veritas-legal`
- Recommended visibility: **PRIVATE CUSTOMER / LEGAL DATA for data-bearing branches; public demo only sanitized**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### CourtListener integration
- Candidate repositories: clairetech2025-max/claire-veritas-legal, clairetech2025-max/claire
- Strongest candidate: claire-veritas-legal for legal product; CLAIRE for integrated demo
- Recommended final repository name: `Claire-Systems/veritas-legal`
- Recommended visibility: **PRIVATE COMMERCIAL**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Azure deployment
- Candidate repositories: clairetech2025-max/claire deployment scripts/nginx/systemd docs
- Strongest candidate: claire monorepo/local VM state
- Recommended final repository name: `Claire-Systems/claire-deployment or private ops folder`
- Recommended visibility: **INTERNAL INFRASTRUCTURE**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Hugging Face deployment
- Candidate repositories: clairetech2025-max/claire hf_space and hf_claire_runtime_full
- Strongest candidate: claire monorepo scaffolds; HF Space currently separate stale Gradio snapshot per prior check
- Recommended final repository name: `Claire-Systems/claire-huggingface-deploy or inside claire`
- Recommended visibility: **PRIVATE DEVELOPMENT / PUBLIC DEMONSTRATION after parity**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### Shared governance infrastructure
- Candidate repositories: clairetech2025-max/claire claire_are, sentinel, diode guard, lane classifier, Claire-Systems/Analog-Recall-Engine-Legacy
- Strongest candidate: claire monorepo current code
- Recommended final repository name: `Claire-Systems/shared-governance or inside claire until stable`
- Recommended visibility: **PRIVATE DEVELOPMENT**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

### DARPA-related prototypes
- Candidate repositories: clairetech2025-max/claire demos/docs, APEX--Verifiable-State, session capsule repos
- Strongest candidate: claire monorepo demos plus APEX prototype
- Recommended final repository name: `Claire-Systems/demos or Claire-Systems/darpa-prototypes-private`
- Recommended visibility: **PRIVATE DEVELOPMENT**
- Consolidation method: transfer if preserving one GitHub repo exactly; merge/import only after branch, tag, and dirty-local-work preservation; archive later only after validation.

