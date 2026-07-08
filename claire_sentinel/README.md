# CLAIRE Sentinel

CLAIRE Sentinel is a defensive security operations and authorized assessment scaffold.

It is not an attack automation system. It blocks unauthorized targets by default, requires an operator reason for every action, requires explicit approval for active scans, and writes an append-only audit record for every allowed or denied attempt.

## Boundaries

- No unauthorized access.
- No credential theft.
- No phishing automation.
- No evasion, persistence, exploitation, or destructive actions.
- Read-only discovery and reporting first.
- Active scans require allowlisted targets and explicit operator approval.

## Basic Commands

Inventory registered tools:

```bash
python -m claire_sentinel.cli inventory
```

Dry-run an approved-target lookup:

```bash
python -m claire_sentinel.cli run dig --target localhost --reason "local DNS smoke test"
```

Execute an active scan only when the target is allowlisted and explicitly approved:

```bash
python -m claire_sentinel.cli --config claire_sentinel/config.example.json run nmap --target 127.0.0.1 --reason "owned local host validation" --approve --execute --arg -Pn --arg --top-ports --arg 20
```

Generate report:

```bash
python -m claire_sentinel.cli report --out claire_state/sentinel/report.md
```

## Controller Integration

`ClaireController.approve_tool_call()` now routes registered security tools through CLAIRE Sentinel before approval.

Controller behavior:

- Guest workers are denied Sentinel security actions.
- Trusted/owner workers still need Sentinel allowlist approval.
- Active scans return `ASK_USER_APPROVAL` until explicit operator approval is present.
- Approved active scans are authorized by the controller, but the controller integration itself performs a dry-run audit only.
- Forbidden/high-risk tools are denied even for trusted/owner workers.

This keeps execution behind policy. A caller must still use `ClaireSentinelRunner` to execute an allowed action.

## ARE Evidence Capsules

Sentinel can write governed ARE memory capsules through `SentinelARECapsuleWriter`.

Capsules store:

- tool name
- target or `local`
- allow/block result
- risk level
- operator reason
- audit ID
- redacted output summary

Capsules do not store raw packet captures, raw logs, credentials, secrets, exploit payloads, or full command output. The dedicated lane is `SENTINEL_SECURITY` with `COMPANY_INTERNAL` scope.

## Configuration

Use a JSON config with an allowlist. Keep real client scopes private and local.

```json
{
  "allow_loopback": true,
  "require_approval_for_active_scans": true,
  "allowlist": ["127.0.0.1", "localhost"]
}
```

## Installed Tool Classes

- Passive discovery: `dig`, `host`, `nslookup`, `whois`, `whatweb`, `wafw00f`
- Configuration audit: `lynis`, `clamscan`, `rkhunter`, `chkrootkit`, `aide`, `oscap`, `ufw`, `iptables`
- Log/offline analysis: `journalctl`, `ausearch`, `aureport`, `tcpdump -r`, `tshark -r`, `yara`
- Active scanning: `nmap`, `nikto`, `gobuster`, `dirb`
- Forbidden/high-risk by default: credential attacks, exploitation frameworks, destructive actions, evasion, persistence, phishing, and high-speed Internet scanning
