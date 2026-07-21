# GitHub Cleanup Final Report

Generated: 2026-07-12T00:48:22.283607Z

## Summary

- Total repositories found: 20
- Repositories under clairetech2025-max: 16
- Repositories under Claire-Systems: 4
- Public count before: 10
- Public count after: 10
- Private count before: 10
- Private count after: 10
- Archived count: 0
- Repositories renamed: 0
- Repositories transferred: 0
- Repositories archived: 0
- Repositories made public: 0
- Repositories kept private: 10

## Repositories Blocked Or Requiring Security Review

- clairetech2025-max/claire
- clairetech2025-max/claire-veritas-legal
- clairetech2025-max/ARE-Librarian
- clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md
- clairetech2025-max/-Claire-Systems-bitbrain-sbc-private
- clairetech2025-max/Claire-Systems-sovereign-execution-gateway-private
- clairetech2025-max/Claire-Systems-are-spectacle-private
- Claire-Systems/.github
- Claire-Systems/Analog-Recall-Engine-Legacy
- Claire-Systems/analog--recall-engine
- Claire-Systems/claire-code-coach-level-1

## Duplicate / Consolidation Families

- clairetech2025-max/session_capsule_protocol -> session-capsule-protocol family
- clairetech2025-max/OfficeAI-500-Sovereign-Mesh-README.md -> OfficeAI-500 family
- clairetech2025-max/claire-code-coach-level-1. -> code-coach duplicate family
- clairetech2025-max/bootstrap_session_capsule_protocol -> session-capsule-protocol family
- clairetech2025-max/AI-Audit-Copilot -> AI-Audit-Copilot duplicate family
- clairetech2025-max/AI-Audit-Copilot- -> AI-Audit-Copilot duplicate family
- clairetech2025-max/OfficeAI-500-Sovereign-Mesh -> OfficeAI-500 family
- clairetech2025-max/ARE -> ARE / analog-recall-engine family
- Claire-Systems/Analog-Recall-Engine-Legacy -> ARE / analog-recall-engine family
- Claire-Systems/analog--recall-engine -> ARE / analog-recall-engine family
- Claire-Systems/claire-code-coach-level-1 -> code-coach duplicate family

## Exact Commands Run

```bash
gh auth status
gh repo list clairetech2025-max --limit 300 --json name,nameWithOwner,visibility,isArchived,description,updatedAt,defaultBranchRef,url,primaryLanguage,diskUsage,issues,pullRequests
gh repo list Claire-Systems --limit 300 --json name,nameWithOwner,visibility,isArchived,description,updatedAt,defaultBranchRef,url,primaryLanguage,diskUsage,issues,pullRequests
gh api repos/OWNER/REPO
gh api repos/OWNER/REPO/contents
gh api repos/OWNER/REPO/license
gh api repos/OWNER/REPO/readme
gh repo clone OWNER/REPO AUDIT_DIR -- --no-tags
git rev-list --objects --all
python3 github_cleanup_audit/analyze_repos.py
python3 github_cleanup_audit/write_reports.py
```

## Errors / Limitations

- `gitleaks` is not installed, so no gitleaks report was produced.
- Empty repositories returned expected API/clone limitations.
- Current public repositories with flags were not changed automatically.
- No visibility, transfer, archive, or rename commands were executed.

## Remaining Manual Decisions

- Decide whether to make currently public flagged repositories private while history cleanup is reviewed.
- Decide license policy for source-available versus open-source repos.
- Approve normalized repository names before rename.
- Approve any transfers to Claire-Systems.
- Install and run gitleaks/trufflehog before approving any private-to-public conversion.
