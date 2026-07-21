# CLAIRE Systems Duplication Analysis

No repositories were merged or modified. Duplicate analysis combines identical-file scan from the prior inventory, local remote grouping, and dirty checkout state.

## Same Remote / Multiple Local Checkouts
### Claire-Systems/.github
- `/home/LuciusPrime/claire/github_cleanup_audit/repo_clones/Claire-Systems__.github` branch `main` dirty `False` ahead/behind `0	0`
- `/home/LuciusPrime/claire_repos/.github` branch `main` dirty `False` ahead/behind `0	0`

### Claire-Systems/analog--recall-engine
- `/home/LuciusPrime/claire/github_cleanup_audit/repo_clones/Claire-Systems__analog--recall-engine` branch `main` dirty `False` ahead/behind `0	0`
- `/home/LuciusPrime/claire_repos/analog--recall-engine` branch `main` dirty `True` ahead/behind `0	0`

### clairetech2025-max/-Claire-Systems-bitbrain-sbc-private
- `/home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__-Claire-Systems-bitbrain-sbc-private` branch `main` dirty `False` ahead/behind `0	0`
- `/home/LuciusPrime/claire/private_repo_payloads/bitbrain-sbc-private` branch `main` dirty `False` ahead/behind `0	0`
- `/home/LuciusPrime/claire_repos/bitbrain-sbc` branch `main` dirty `False` ahead/behind `0	0`

### clairetech2025-max/Claire-Systems-are-spectacle-private
- `/home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__Claire-Systems-are-spectacle-private` branch `main` dirty `False` ahead/behind `0	0`
- `/home/LuciusPrime/claire/private_repo_payloads/are-spectacle-private` branch `main` dirty `False` ahead/behind `0	0`

### clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private
- `/home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__Claire-Systems-sovereign-execution-gateway-private` branch `main` dirty `False` ahead/behind `0	0`
- `/home/LuciusPrime/claire/private_repo_payloads/sovereign-execution-gateway-private` branch `main` dirty `False` ahead/behind `0	0`

### clairetech2025-max/claire
- `/home/LuciusPrime/claire` branch `codex/venture-intelligence-slice-1` dirty `True` ahead/behind `0	0`
- `/home/LuciusPrime/claire-odyssey` branch `main` dirty `True` ahead/behind `0	0`
- `/home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__claire` branch `main` dirty `False` ahead/behind `0	0`
- `/home/LuciusPrime/odyssey-claire-build` branch `main` dirty `True` ahead/behind `0	0`

### clairetech2025-max/claire-veritas-legal
- `/home/LuciusPrime/claire/github_cleanup_audit/repo_clones/clairetech2025-max__claire-veritas-legal` branch `main` dirty `False` ahead/behind `0	0`
- `/home/LuciusPrime/claire_repos/claire-veritas-legal` branch `main` dirty `True` ahead/behind `0	0`

## Product Duplication / Divergence Notes
- `clairetech2025-max/claire` has multiple local checkouts (`/home/LuciusPrime/claire`, `/home/LuciusPrime/claire-odyssey`, `/home/LuciusPrime/odyssey-claire-build`) with dirty local work. Do not transfer or consolidate until those local changes are preserved as branches or patches.
- `clairetech2025-max/claire-veritas-legal` has a clean audit clone plus dirty live checkout at `/home/LuciusPrime/claire_repos/claire-veritas-legal` containing `web/services/llm.py` changes and local runtime artifacts.
- `Claire-Systems/analog--recall-engine` has a dirty local checkout with README and benchmark additions; preserve before declaring public ARE canonical.
- `Claire-Systems/Analog-Recall-Engine-Legacy`, `Claire-Systems/analog--recall-engine`, `clairetech2025-max/ARE-Librarian`, and `clairetech2025-max/claire` all overlap conceptually around ARE/Librarian. They are not automatic duplicates; they represent legacy public reference, minimal public repo, private Librarian candidate, and active integrated implementation respectively.
- `session_capsule_protocol` and `bootstrap_session_capsule_protocol` are related but should be treated as protocol docs vs starter/bootstrap until manually compared.
