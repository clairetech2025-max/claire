from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
REQUIRED_SCOPES = frozenset({DRIVE_READONLY_SCOPE})
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class CredentialSafetyError(RuntimeError):
    pass


def external_credential_path(value: str | Path, *, label: str, must_exist: bool = False) -> Path:
    raw = Path(value).expanduser()
    if not raw.is_absolute():
        raise CredentialSafetyError(f"{label} must be an absolute path outside the repository")
    if raw.is_symlink():
        raise CredentialSafetyError(f"{label} must not be a symbolic link")
    resolved = raw.resolve(strict=False)
    if resolved == REPOSITORY_ROOT or REPOSITORY_ROOT in resolved.parents:
        raise CredentialSafetyError(f"{label} must be outside {REPOSITORY_ROOT}")
    if must_exist and (not resolved.is_file() or resolved.is_symlink()):
        raise CredentialSafetyError(f"{label} must be an existing regular file")
    return resolved


def normalized_scopes(scopes: Iterable[str] | str | None) -> frozenset[str]:
    if scopes is None:
        return frozenset()
    values = scopes.split() if isinstance(scopes, str) else scopes
    return frozenset(str(scope).strip() for scope in values if str(scope).strip())


def require_exact_readonly_scopes(scopes: Iterable[str] | str | None, *, label: str) -> None:
    effective = normalized_scopes(scopes)
    if effective != REQUIRED_SCOPES:
        raise CredentialSafetyError(
            f"{label} must grant exactly drive.readonly; missing or broader scopes are rejected"
        )


def require_exact_credential_scopes(credentials: Any) -> None:
    granted = getattr(credentials, "granted_scopes", None)
    declared = getattr(credentials, "scopes", None)
    require_exact_readonly_scopes(granted if granted is not None else declared, label="Google credentials")


def validate_authorized_user_token_file(path: str | Path) -> Path:
    safe_path = external_credential_path(path, label="OAuth token file", must_exist=True)
    try:
        payload = json.loads(safe_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CredentialSafetyError("OAuth token file is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise CredentialSafetyError("OAuth token file must contain a JSON object")
    require_exact_readonly_scopes(payload.get("scopes"), label="OAuth token file")
    return safe_path
