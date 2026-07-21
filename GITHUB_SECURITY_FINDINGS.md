# GitHub Security Findings

Audit mode: no repositories were modified. Findings are redacted and current-tree only unless noted. False-positive-prone token variable matches are marked REVIEW, not CRITICAL.

## Claire-Systems/.github
Visibility: PUBLIC | Recommended action: SAFE TO KEEP PUBLIC
- REVIEW: email address at `profile/README.md:36` sample `lice****s.ai`

## Claire-Systems/Analog-Recall-Engine-Legacy
Visibility: PUBLIC | Recommended action: NEEDS SECURITY REVIEW
- REVIEW: email address at `README.md:198` sample `lice****s.ai`
- REVIEW: email address at `README.md:216` sample `lice****s.ai`

## Claire-Systems/analog--recall-engine
Visibility: PUBLIC | Recommended action: NEEDS SECURITY REVIEW
- REVIEW: email address at `README.md:90` sample `lice****s.ai`
- REVIEW: email address at `README.md:111` sample `lice****s.ai`
- REVIEW: email address at `LICENSE:14` sample `lice****s.ai`
- REVIEW: email address at `LICENSE:22` sample `lice****s.ai`

## Claire-Systems/claire-code-coach-level-1
Visibility: PRIVATE | Recommended action: NEEDS SECURITY REVIEW
- REVIEW: token assignment at `claire_ai.py:178` sample `api_****get(` — Code variable/parameter pattern; review manually, not confirmed exposed secret.

## clairetech2025-max/-Claire-Systems-bitbrain-sbc-private
Visibility: PUBLIC | Recommended action: MAKE PRIVATE
- REVIEW: email address at `README.md:147` sample `lice****s.ai`
- REVIEW: email address at `README.md:173` sample `lice****s.ai`
- REVIEW: email address at `LICENSE:25` sample `lice****s.ai`
- REVIEW: email address at `LICENSE:33` sample `lice****s.ai`

## clairetech2025-max/ARE-Librarian
Visibility: PRIVATE | Recommended action: NEEDS SECURITY REVIEW
- REVIEW: token assignment at `src/are_sidecar.py:108` sample `toke****rip(` — Code variable/parameter pattern; review manually, not confirmed exposed secret.

## clairetech2025-max/Claire-Systems-are-spectacle-private
Visibility: PRIVATE | Recommended action: NEEDS SECURITY REVIEW
- REVIEW: local absolute path at `DEPLOYMENT.md:37` sample `/hom****.log`

## clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md
Visibility: PUBLIC | Recommended action: SAFE TO KEEP PUBLIC
- REVIEW: email address at `README.md:224` sample `lice****s.ai`
- REVIEW: email address at `README.md:251` sample `lice****s.ai`
- REVIEW: email address at `LICENSE:25` sample `lice****s.ai`
- REVIEW: email address at `LICENSE:33` sample `lice****s.ai`

## clairetech2025-max/claire
Visibility: PUBLIC | Recommended action: NEEDS SECURITY REVIEW
- REVIEW: local absolute path at `claire_parser:564` sample `/hom****sonl`
- REVIEW: local absolute path at `claire_parser:569` sample `/hom****temp`
- REVIEW: local absolute path at `claire_core_v1.py:232` sample `/hom****e_v1`
- REVIEW: local absolute path at `LAUNCH.sh:8` sample `/hom****aire`
- REVIEW: local absolute path at `claire_pulse_final.sh:13` sample `/hom****e.go`
- REVIEW: local absolute path at `run_are.sh:3` sample `/hom****aire`
- REVIEW: email address at `MARKET_ANALYSIS_REPORT.md:84` sample `lice****s.ai`
- REVIEW: local absolute path at `claire_parser.py:668` sample `/hom****sonl`
- REVIEW: local absolute path at `claire_parser.py:673` sample `/hom****temp`
- REVIEW: local absolute path at `centaur_demo.sh.:3` sample `/hom****data`
- REVIEW: local absolute path at `centaur_demo.sh.:4` sample `/hom****logs`
- REVIEW: local absolute path at `ARE_SERVER.py:14` sample `/hom****sonl`
- REVIEW: local absolute path at `claire_reader.py:24` sample `/hom****aire`
- REVIEW: local absolute path at `claire_sovereign_boot.sh:8` sample `/hom****.env`
- REVIEW: local absolute path at `claire_sovereign_boot.sh:10` sample `/hom****.env`
- REVIEW: local absolute path at `claire_sovereign_boot.sh:19` sample `/hom****aire`
- REVIEW: local absolute path at `claire_sovereign_boot.sh:38` sample `/hom****edge`
- REVIEW: Azure connection string at `claire_azure_sync.py:1` sample `Defa****+w==` — Looks like placeholder/example connection string; still unsafe pattern for a public repo and should be replaced with env-based example.
- REVIEW: local absolute path at `claire_bootstrap.sh:7` sample `/hom****aire`
- REVIEW: local absolute path at `claire_are_loader.py:6` sample `/hom****sonl`
- REVIEW: local absolute path at `claire_ingest_bridge.py:12` sample `/hom****aire`
- REVIEW: local absolute path at `bootstrap.sh:14` sample `/hom****aire`
- REVIEW: local absolute path at `bootstrap.sh:17` sample `/hom****vate`
- REVIEW: local absolute path at `bootstrap.sh:18` sample `/hom****.log`
- REVIEW: local absolute path at `bootstrap.sh:22` sample `/hom****rver`
- REVIEW: local absolute path at `bootstrap.sh:23` sample `/hom****gguf`
- REVIEW: local absolute path at `bootstrap.sh:24` sample `/hom****.log`
- REVIEW: local absolute path at `bootstrap.sh:29` sample `/hom****.log`
- REVIEW: local absolute path at `recovered_claire_gui.py:4` sample `/hom****i.py`
- REVIEW: token assignment at `claire_scholar.py:137` sample `api_****get(` — Code variable/parameter pattern; review manually, not confirmed exposed secret.
- REVIEW: local absolute path at `claire_reflect.py:24` sample `/hom****aire`
- REVIEW: local absolute path at `sovereign_proxy.go:8` sample `/hom****eam_`
- REVIEW: local absolute path at `sovereign_proxy.go:13` sample `/hom****.pem`
- REVIEW: local absolute path at `claire_bootstrap_v2.sh:16` sample `/hom****e.go`
- REVIEW: token assignment at `claire_courtlistener.py:24` sample `toke****env(` — Code variable/parameter pattern; review manually, not confirmed exposed secret.
- REVIEW: local absolute path at `sentinel_core/sentinel_ingest.py:10` sample `/hom****aire`
- REVIEW: local absolute path at `sentinel_core/are_server.py:6` sample `/hom****sonl`
- REVIEW: local absolute path at `gumroad_builds/CREATE_PRIVATE_REPOS.md:41` sample `/hom****vate`
- REVIEW: email address at `gumroad_builds/CREATE_PRIVATE_REPOS.md:46` sample `git@****.com`
- REVIEW: local absolute path at `gumroad_builds/CREATE_PRIVATE_REPOS.md:69` sample `/hom****d.sh`

## clairetech2025-max/claire-veritas-legal
Visibility: PUBLIC | Recommended action: NEEDS SECURITY REVIEW
- REVIEW: email address at `edgar_client.py:15` sample `stev****s.ai`
- REVIEW: token assignment at `courtlistener_client.py:68` sample `toke****str]` — Code variable/parameter pattern; review manually, not confirmed exposed secret.
- REVIEW: token assignment at `tests/test_courtlistener_client.py:39` sample `toke****test` — Code variable/parameter pattern; review manually, not confirmed exposed secret.
- REVIEW: token assignment at `tests/test_courtlistener_client.py:57` sample `toke****test` — Code variable/parameter pattern; review manually, not confirmed exposed secret.
- REVIEW: token assignment at `tests/test_courtlistener_client.py:72` sample `toke****test` — Code variable/parameter pattern; review manually, not confirmed exposed secret.
- REVIEW: token assignment at `tests/test_courtlistener_client.py:80` sample `toke****test` — Code variable/parameter pattern; review manually, not confirmed exposed secret.
- REVIEW: phone-like at `tests/test_veritas_firm_authority.py:42` sample `555)****0100`
- REVIEW: email address at `tests/test_veritas_firm_authority.py:43` sample `firm****.com`
- REVIEW: email address at `tests/test_veritas_firm_authority.py:60` sample `jord****.com`
- REVIEW: phone-like at `tests/test_veritas_firm_authority.py:61` sample `555)****0101`
- REVIEW: email address at `tests/test_veritas_firm_authority.py:73` sample `case****.com`
- REVIEW: email address at `tests/test_veritas_firm_authority.py:85` sample `tayl****.com`
- REVIEW: phone-like at `web/index.html:447` sample `000)****0000`
- REVIEW: email address at `web/index.html:451` sample `firm****.com`
- REVIEW: email address at `web/index.html:504` sample `alex****.com`
- REVIEW: phone-like at `web/index.html:508` sample `000)****0000`
- REVIEW: token assignment at `web/app.py:1202` sample `toke****get(` — Code variable/parameter pattern; review manually, not confirmed exposed secret.

Note: if a real secret exists in Git history, deleting the current file alone will not remove it from history. This run used shallow clones plus available local checkout evidence, so full history scanning remains a follow-up for any repository being kept public.
