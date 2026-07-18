from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import ActionRequest
from .policy import SentinelPolicy
from .report import SentinelReportGenerator
from .runner import ClaireSentinelRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLAIRE Sentinel defensive security runner")
    parser.add_argument("--config", default="", help="Optional JSON policy config with allowlist")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inventory", help="List registered tools and local install status")

    run = sub.add_parser("run", help="Run a policy-gated Sentinel action")
    run.add_argument("tool")
    run.add_argument("--target", default="")
    run.add_argument("--reason", required=True)
    run.add_argument("--arg", action="append", default=[])
    run.add_argument("--approve", action="store_true", help="Explicit approval for active scans")
    run.add_argument("--execute", action="store_true", help="Execute instead of dry-run")

    report = sub.add_parser("report", help="Write a Sentinel markdown report")
    report.add_argument("--out", default="claire_state/sentinel/report.md")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    policy = SentinelPolicy.from_json(args.config) if args.config else SentinelPolicy()
    runner = ClaireSentinelRunner(policy=policy)

    if args.command == "inventory":
        print(json.dumps(runner.inventory(), indent=2))
        return
    if args.command == "run":
        result = runner.run(ActionRequest(
            tool=args.tool,
            target=args.target,
            reason=args.reason,
            args=tuple(args.arg),
            operator_approved=args.approve,
            dry_run=not args.execute,
        ))
        print(json.dumps({
            "audit_id": result.audit_id,
            "allowed": result.decision.allowed,
            "reason": result.decision.reason,
            "command": result.command,
            "output_summary": result.output_summary,
        }, indent=2))
        return
    if args.command == "report":
        path = SentinelReportGenerator().write_markdown(Path(args.out))
        print(str(path))


if __name__ == "__main__":
    main()
