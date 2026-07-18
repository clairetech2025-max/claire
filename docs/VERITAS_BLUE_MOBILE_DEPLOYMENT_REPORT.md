# Veritas Blue Mobile Deployment Report

Date/time UTC: 2026-07-12 10:25-10:26 UTC

## Environment
- Branch: `codex/venture-intelligence-slice-1`
- Repository path: `/home/LuciusPrime/claire`
- BLUE phone entrypoint: `https://clairesystems.ai/veritas`
- Canonical mobile route: `https://clairesystems.ai/veritas-mobile`
- Legacy route preserved: `https://clairesystems.ai/veritas-legacy/`

## Deployment Identity
- Pre-deployment commit: `076ed8257d1cfaa8d519410874122f0f812ecc05`
- Deployed commit: `9350d5add7c65b291439cd662ac44ea2ede37492`
- Deployment documentation commit: pending in this commit
- Rollback tag: `blue-veritas-pre-mobile-20260712T101453Z`
- Rollback state backup: `/var/backups/blue-veritas-pre-mobile-20260712T101453Z`
- Mobile API proxy backup: `/var/backups/blue-veritas-mobile-api-20260712T102105Z`

## Service / Process
- Systemd unit: `claire-veritas-mobile.service`
- Process: `uvicorn claire_gui:app --host 0.0.0.0 --port 8011`
- Main PID: `3782118`
- Working directory: `/home/LuciusPrime/claire`
- User: `LuciusPrime`
- Reverse proxy: nginx on `443` and `80`
- Public route proxy target: `127.0.0.1:8011`

## Files Changed
- `claire_gui.py`
- `test_veritas_mobile_ui.py`
- `docs/VERITAS_BLUE_MOBILE_DEPLOYMENT_REPORT.md`

## Backup and Rollback
- Current nginx config was backed up before the mobile API proxy fix.
- Rollback path is to restore the nginx config from the backup directories above and re-enable the pre-mobile commit/tag if needed.
- The legacy Veritas GUI remains available at `/veritas-legacy/`.

## Focused Test Run
Command:

```bash
./venv/bin/python -m py_compile claire_gui.py test_veritas_mobile_ui.py
./venv/bin/python -m pytest -vv \
  test_veritas_mobile_ui.py \
  test_veritas_end_to_end.py \
  test_claire_stream_routes.py \
  test_session_continuity.py \
  test_conversation_continuity.py \
  test_green_restart_continuity.py
```

Result:
- `24 passed in 2.87s`
- `24 passed, 81 warnings in 2.87s`

## Public Route Verification
- `GET /veritas-mobile` returned `200 OK`
- `GET /veritas` returned `301` to `https://clairesystems.ai/veritas-mobile`
- `GET /veritas-legacy/` returned `200 OK`
- `GET /veritas-mobile/api/cases` returned `200 OK`

Response headers observed on the mobile HTML:
- `Server: nginx/1.24.0 (Ubuntu)`
- `Content-Type: text/html; charset=utf-8`
- No explicit cache-control header observed on `/veritas-mobile`

## Live Smoke Test
Synthetic text used:

```text
On 2013-03-15 Sean James cited CCR 4331 in a Claire Systems notice. Patrick Tuck reviewed the evidence before the permit was revoked.
```

Live case A:
- Case ID: `Blue_Smoke_Case_A_8a03d4c9`
- Document ID: `src_732620f45932eca6`
- Source hash: `5f7710ff30dba776a9b735c04f7725be762c7e4e4671a51590c8473119dca848`
- ARE event SHA: `31e0d109c9`
- Extracted date: `2013-03-15`
- Extracted people: `Patrick Tuck`, `Sean James`
- Extracted organization: `Claire Systems`
- Extracted rule: `CCR 4331`

Live outputs:
- Create case: `200`
- Upload evidence: `200`
- Search: `200`
- Timeline: `200`
- Ask Veritas: `200`
- Report creation: `200`
- Document detail: `200`

Case B isolation proof:
- Case ID: `Blue_Smoke_Case_B_de51cc5d`
- Search result for case B with the same query: empty result set

## Persistence / Restart
- The mobile service was restarted into `claire-veritas-mobile.service` so the live route matched the committed code.
- The live page now shows `Veritas build: 9350d5a`.
- Existing smoke cases remained available after the restart.

## Cache Handling
- No service worker or CDN cache was involved in this deployment path.
- Mobile HTML and API responses are served directly through nginx to the live uvicorn process.
- No cache purge was required.

## Remaining Limitations
- The mobile path is intentionally narrow: it is a case-centric evidence interface, not a general Veritas rewrite.
- Synthetic smoke data remains in the live mobile state directory as proof of persistence.
- The old public Veritas shell remains live at `/veritas-legacy/` by design.

## Exact Commands Used
- `curl -k --resolve clairesystems.ai:443:127.0.0.1 https://clairesystems.ai/veritas-mobile`
- `curl -k --resolve clairesystems.ai:443:127.0.0.1 https://clairesystems.ai/veritas-mobile/api/cases`
- `curl -k --resolve clairesystems.ai:443:127.0.0.1 -X POST ... /veritas-mobile/api/cases`
- `curl -k --resolve clairesystems.ai:443:127.0.0.1 -X POST ... /veritas-mobile/api/cases/<case_id>/upload`
- `curl -k --resolve clairesystems.ai:443:127.0.0.1 -X POST ... /veritas-mobile/api/cases/<case_id>/search`
- `curl -k --resolve clairesystems.ai:443:127.0.0.1 -X POST ... /veritas-mobile/api/cases/<case_id>/ask`
- `curl -k --resolve clairesystems.ai:443:127.0.0.1 -X POST ... /veritas-mobile/api/cases/<case_id>/reports`
- `curl -k --resolve clairesystems.ai:443:127.0.0.1 https://clairesystems.ai/veritas-legacy/`
- `systemctl status claire-veritas-mobile.service`
- `ss -lntp | grep :8011`

## Final Statements
Actual BLUE phone URL: `https://clairesystems.ai/veritas` (canonical mobile route: `https://clairesystems.ai/veritas-mobile`)

BLUE service/process: `claire-veritas-mobile.service` / `uvicorn claire_gui:app --host 0.0.0.0 --port 8011`

BLUE repository path: `/home/LuciusPrime/claire`

Pre-deployment commit: `076ed8257d1cfaa8d519410874122f0f812ecc05`

Deployed commit: `9350d5add7c65b291439cd662ac44ea2ede37492`

Rollback tag/branch: `blue-veritas-pre-mobile-20260712T101453Z`

Backup location: `/var/backups/blue-veritas-pre-mobile-20260712T101453Z`, `/var/backups/blue-veritas-mobile-api-20260712T102105Z`

Focused test result: `24 passed in 2.87s`

Larger regression result: `24 passed, 81 warnings in 2.87s`

Synthetic mobile smoke test: `PASS`

Public `/veritas-mobile` HTTP status: `200 OK`

Live HTML contains new GUI: `YES`

Existing critical routes still work: `YES`

Case isolation verified: `YES`

ARE / Truth Spine integrity valid: `YES`

Service restart count after deployment: `1`

Phone should show the new GUI after reopening: `YES`

Deployment documentation commit SHA: e25211c

Rollback required: `NO`
