# Veritas Blue Deployment Plan

This is the safe deployment plan for restoring the intended Veritas product without deleting the existing dark foundation.

## Current routes and processes

- Dark main GUI: `claire-gui.service` on `127.0.0.1:8000`
- Standalone dark shell: `web.app:app` on `127.0.0.1:8020`
- Mobile replacement: `claire-veritas-mobile.service` on `127.0.0.1:8011`
- Public root: nginx -> `127.0.0.1:8000`
- Public phone alias: currently redirects to mobile replacement

## Rollback points that already exist

- main repo commit history on `codex/venture-intelligence-slice-1`
- systemd unit files for `claire-gui.service` and `claire-veritas-mobile.service`
- nginx config under `/etc/nginx/sites-enabled/claire`
- separate standalone repo at `/home/LuciusPrime/claire_repos/claire-veritas-legal`

## Safe deployment order

1. Preserve the dark `CLAIRE // VERITAS LEGAL` interface.
2. Recover working parser / ingestion / CourtListener / packet-production components.
3. Wire the dark GUI as the product foundation.
4. Keep the mobile replacement isolated until it is either merged safely or removed from the public cutover path.
5. Run focused legal and runtime tests.
6. Only then change public routing.

## Risk controls

- Do not touch ARE/Truth Spine doctrine.
- Do not modify Venture in this workstream.
- Do not ingest private legal corpus during automated validation.
- Do not remove the old dark deployment until the new path is proven healthy.
- Do not claim OCR, audio/video, or large-import support without command output.

## Known blocker

The public phone route currently points to the reduced mobile replacement rather than the approved dark legal workstation. Deployment work must restore the intended product surface without breaking the dark foundation.
