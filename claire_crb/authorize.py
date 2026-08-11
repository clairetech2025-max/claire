from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from .oauth_security import (
    DRIVE_READONLY_SCOPE,
    CredentialSafetyError,
    external_credential_path,
    require_exact_credential_scopes,
)


AUTHORIZATION_PROMPT = "Open this authorization URL in the Android browser:\n{url}"
AUTHORIZATION_SUCCESS = "Authorization received. Return to the Ubuntu/proot terminal."


def _installed_app_flow_factory(client_file: str, scopes: list[str]) -> Any:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Google authorization dependencies are not installed; install the project 'crb' optional dependencies."
        ) from exc
    return InstalledAppFlow.from_client_secrets_file(client_file, scopes)


def _secure_write_token(token_file: Path, serialized_credentials: str) -> None:
    parent = token_file.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise CredentialSafetyError("OAuth token parent must be a real directory")
    os.chmod(parent, 0o700)
    if token_file.exists() and (token_file.is_symlink() or not token_file.is_file()):
        raise CredentialSafetyError("OAuth token destination must be a regular file")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".google-token-", suffix=".tmp", dir=parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(serialized_credentials)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, token_file)
        os.chmod(token_file, 0o600)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path.exists():
            temporary_path.unlink()


def authorize_desktop_client(
    *,
    client_file: str | Path,
    token_file: str | Path,
    open_browser: bool,
    flow_factory: Callable[[str, list[str]], Any] | None = None,
) -> Path:
    safe_client = external_credential_path(client_file, label="OAuth client file", must_exist=True)
    safe_token = external_credential_path(token_file, label="OAuth token file")
    if safe_client == safe_token:
        raise CredentialSafetyError("OAuth client and token paths must be different")
    flow = (flow_factory or _installed_app_flow_factory)(str(safe_client), [DRIVE_READONLY_SCOPE])
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=bool(open_browser),
        authorization_prompt_message=AUTHORIZATION_PROMPT,
        success_message=AUTHORIZATION_SUCCESS,
        access_type="offline",
        prompt="consent",
    )
    require_exact_credential_scopes(credentials)
    _secure_write_token(safe_token, credentials.to_json())
    print(f"Authorized-user token written securely to {safe_token}")
    return safe_token


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Authorize CLAIRE CRB for read-only Google Drive access")
    parser.add_argument("--client-file", required=True, help="Absolute external path to Desktop OAuth client JSON")
    parser.add_argument("--token-file", required=True, help="Absolute external path for authorized-user token JSON")
    parser.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Print the authorization URL while the 127.0.0.1 callback listener remains active",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        authorize_desktop_client(
            client_file=args.client_file,
            token_file=args.token_file,
            open_browser=not args.no_open_browser,
        )
    except (CredentialSafetyError, RuntimeError) as exc:
        print(f"Authorization failed safely: {exc}", file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
