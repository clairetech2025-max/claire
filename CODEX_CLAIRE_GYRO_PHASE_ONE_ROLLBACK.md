# CODEX CLAIRE GYRO PHASE ONE ROLLBACK

Status: planning only. Do not implement until `APPROVED PHASE ONE CHANGE PLAN`.

## Rollback Goal

Return the repository to the pre-Phase-One application-code state without touching the protected WIP snapshot branch, production branch, runtime databases, secrets, package files, or GUI assets.

## Pre-Change Hashes

- `claire_gui.py`: `3de33536783fcd9f323bf5e9ecf95d45b6454b137aa9851b170e382ef09e2be7`
- `intent_classifier.py`: `94712a223b11bff097212239ed47c2acdb57c502e13678b114b8e038199a7eed`
- `lane_router.py`: `d252fb21f074848251a7c8e86145e98b5018cd5dc21d0216bdfdd578ae5df0fe`
- `relevance_gate.py`: `d1286a41254bea7cb3fad9c7c536934f2b077bc56b34b2f399404d4779e908ac`
- `answer_planner.py`: `c8f08fea70851912437aadc1bc6821ef80ceeae2cba38797d70e8105708d4354`
- `test_memory_routing.py`: `08089d5d80c9ee937072afa6d615a9a5724a0e0c68ac447c922cad8e1b845f8d`

## Files That May Need Rollback

- `claire_gui.py`
- `intent_classifier.py`
- `lane_router.py`
- `relevance_gate.py`
- `answer_planner.py`
- `test_memory_routing.py`
- `claire_runtime_router.py`
- `memory_eligibility.py`
- `write_barrier.py`

## Protected GUI Baseline

Protected GUI-facing file hashes from Phase Zero:

- `claire_gui.py`: `3de33536783fcd9f323bf5e9ecf95d45b6454b137aa9851b170e382ef09e2be7`
- `templates/index.html`: `6643312b1366a71dc8bd0008d740c59d6998b80e2cba6080c3fdc87d5b776908`
- `claire_gui.html`: `578ad1827a27a66089af27fbaa7463958a5165774241baf814c42d1f0b457a06`
- `static/logo.png`: `68620b1b930c4240744f61325aeeeaf408c72dde6855f4e41d29b92568335168`
- `static/claire_waveform.jpg`: `65bf3553cdf5e082c2e46f67476288fc40aee27b13e0b8c2d22baa3c4e0415ef`

Protected visible ranges in `claire_gui.py`:

- 1038-5881
- 12442-12764
- 13174-13277

## Rollback Procedure

1. Stop work immediately if Phase One tests show context contamination, GUI changes, provider breakage, or writeback violations.
2. Do not run destructive Git commands unless explicitly approved.
3. Revert only the Phase One application-code edits using a targeted patch.
4. Remove new Phase One modules only if they are part of the failed change and explicitly approved for removal.
5. Preserve audit and plan files unless asked to remove them.
6. Verify hashes for unaffected protected GUI files.
7. If `claire_gui.py` changed, verify protected visible ranges have no diff.
8. Run the routing test file and compile check if available.
9. Report exact files restored and any remaining untracked files.

## Non-Destructive Recovery Points

- Remote WIP snapshot branch: `codex/claire-pre-refactor-snapshot`
- WIP snapshot commit: `5a40ce8`
- Clean repair base: `origin/main` at `a742aae`
- Current branch for Phase One planning: `codex/claire-backend-repair`

## Explicit Non-Rollback Items

Do not delete or alter:

- `.env` files
- runtime databases
- `data/` contents
- `package-lock.json` unless separately approved
- production branches
- remote branches
- GUI assets
- service processes

## Success Criteria After Rollback

- Application-code files match pre-Phase-One hashes or have documented approved differences.
- Protected GUI visible ranges are unchanged.
- No new service state or package state was created.
- Working tree status is understood and reported.



## Post-Implementation Rollback Detail

New files to remove or leave untracked during rollback, depending on approval:

- `claire_runtime_router.py`
- `memory_eligibility.py`
- `write_barrier.py`
- `test_phase_one_runtime.py`
- `CODEX_CLAIRE_GYRO_PHASE_ONE_IMPLEMENTATION_LOG.md`

`claire_gui.py` original hash preserved:

`3de33536783fcd9f323bf5e9ecf95d45b6454b137aa9851b170e382ef09e2be7`

`claire_gui.py` post-implementation hash:

`88cc9d6177f37828a5af92078147065077b17c5db0318d5ab0b866f532dab6e1`

Rollback patch target:

- remove `route_chat_message` import and fallback
- remove `persist_phase_one_trace()`
- remove `finalize_phase_one_reply()`
- restore prior `build_reply()` body from pre-Phase-One state

Do not use destructive Git commands without approval.
