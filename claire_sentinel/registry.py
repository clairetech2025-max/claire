from __future__ import annotations

import shutil
from typing import Iterable

from .models import ToolCategory, ToolDefinition, ToolRisk


class SentinelToolRegistry:
    """Static defensive registry plus local command inventory."""

    def __init__(self, tools: Iterable[ToolDefinition] | None = None) -> None:
        self._tools = {tool.name: tool for tool in (tools or DEFAULT_TOOLS)}

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(str(name).lower())

    def all(self) -> list[ToolDefinition]:
        return sorted(self._tools.values(), key=lambda tool: tool.name)

    def installed_inventory(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for tool in self.all():
            path = shutil.which(tool.command)
            rows.append({
                **tool.to_dict(),
                "installed": bool(path),
                "path": path or "",
            })
        return rows


DEFAULT_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition("dig", ToolCategory.PASSIVE_DISCOVERY, ToolRisk.LOW, True, False, "dig", "DNS lookup for approved targets."),
    ToolDefinition("host", ToolCategory.PASSIVE_DISCOVERY, ToolRisk.LOW, True, False, "host", "DNS lookup for approved targets."),
    ToolDefinition("nslookup", ToolCategory.PASSIVE_DISCOVERY, ToolRisk.LOW, True, False, "nslookup", "DNS lookup for approved targets."),
    ToolDefinition("whois", ToolCategory.PASSIVE_DISCOVERY, ToolRisk.LOW, True, False, "whois", "WHOIS lookup for approved targets."),
    ToolDefinition("whatweb", ToolCategory.PASSIVE_DISCOVERY, ToolRisk.MEDIUM, True, False, "whatweb", "Passive web fingerprinting for approved targets."),
    ToolDefinition("wafw00f", ToolCategory.PASSIVE_DISCOVERY, ToolRisk.MEDIUM, True, False, "wafw00f", "WAF fingerprinting for approved targets."),
    ToolDefinition("ss", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "ss", "Local socket inspection."),
    ToolDefinition("lsof", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "lsof", "Local open-file and socket inspection."),
    ToolDefinition("ufw", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "ufw", "Local firewall status inspection."),
    ToolDefinition("iptables", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "iptables", "Local firewall rule inspection."),
    ToolDefinition("journalctl", ToolCategory.LOG_ANALYSIS, ToolRisk.LOW, False, False, "journalctl", "Local journal log review."),
    ToolDefinition("ausearch", ToolCategory.LOG_ANALYSIS, ToolRisk.LOW, False, False, "ausearch", "Local audit log search."),
    ToolDefinition("aureport", ToolCategory.LOG_ANALYSIS, ToolRisk.LOW, False, False, "aureport", "Local audit report generation."),
    ToolDefinition("tcpdump-read", ToolCategory.LOG_ANALYSIS, ToolRisk.LOW, False, False, "tcpdump", "Offline PCAP summary only.", allowed_args=("-nn", "-r", "-c")),
    ToolDefinition("tshark-read", ToolCategory.LOG_ANALYSIS, ToolRisk.LOW, False, False, "tshark", "Offline PCAP summary only.", allowed_args=("-r", "-c")),
    ToolDefinition("yara", ToolCategory.LOG_ANALYSIS, ToolRisk.LOW, False, False, "yara", "Local YARA scan of provided files."),
    ToolDefinition("clamscan", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "clamscan", "Local malware scan."),
    ToolDefinition("lynis", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "lynis", "Local host security audit."),
    ToolDefinition("rkhunter", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "rkhunter", "Local rootkit check."),
    ToolDefinition("chkrootkit", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "chkrootkit", "Local rootkit check."),
    ToolDefinition("aide", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "aide", "Local file integrity check."),
    ToolDefinition("oscap", ToolCategory.CONFIGURATION_AUDIT, ToolRisk.LOW, False, False, "oscap", "Local compliance scanner."),
    ToolDefinition("nmap", ToolCategory.VULNERABILITY_SCANNING, ToolRisk.HIGH, True, True, "nmap", "Approved-target port/service scan."),
    ToolDefinition("nikto", ToolCategory.VULNERABILITY_SCANNING, ToolRisk.HIGH, True, True, "nikto", "Approved-target web vulnerability scan."),
    ToolDefinition("gobuster", ToolCategory.VULNERABILITY_SCANNING, ToolRisk.HIGH, True, True, "gobuster", "Approved-target content discovery."),
    ToolDefinition("dirb", ToolCategory.VULNERABILITY_SCANNING, ToolRisk.HIGH, True, True, "dirb", "Approved-target content discovery."),
    ToolDefinition("masscan", ToolCategory.FORBIDDEN_HIGH_RISK, ToolRisk.FORBIDDEN, True, True, "masscan", "High-speed scanning is forbidden by default."),
    ToolDefinition("sqlmap", ToolCategory.FORBIDDEN_HIGH_RISK, ToolRisk.FORBIDDEN, True, True, "sqlmap", "Automated exploitation is forbidden by default."),
    ToolDefinition("hydra", ToolCategory.FORBIDDEN_HIGH_RISK, ToolRisk.FORBIDDEN, True, True, "hydra", "Credential attacks are forbidden."),
    ToolDefinition("msfconsole", ToolCategory.FORBIDDEN_HIGH_RISK, ToolRisk.FORBIDDEN, True, True, "msfconsole", "Exploit framework use is forbidden by default."),
    ToolDefinition("john", ToolCategory.FORBIDDEN_HIGH_RISK, ToolRisk.FORBIDDEN, False, False, "john", "Credential cracking is forbidden."),
    ToolDefinition("hashcat", ToolCategory.FORBIDDEN_HIGH_RISK, ToolRisk.FORBIDDEN, False, False, "hashcat", "Credential cracking is forbidden."),
)
