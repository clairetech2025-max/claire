from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

import pytest

from claire_crb.authorize import AUTHORIZATION_PROMPT, authorize_desktop_client
from claire_crb.google_drive import GoogleDriveCredentialError, load_readonly_credentials
from claire_crb.oauth_security import (
    DRIVE_READONLY_SCOPE,
    CredentialSafetyError,
    validate_authorized_user_token_file,
)


class FakeCredentials:
    def __init__(self, scopes, serialized: str):
        self.scopes = scopes
        self.granted_scopes = scopes
        self._serialized = serialized

    def to_json(self):
        return self._serialized


class FakeFlow:
    def __init__(self, credentials):
        self.credentials = credentials
        self.run_kwargs = None

    def run_local_server(self, **kwargs):
        self.run_kwargs = kwargs
        if not kwargs["open_browser"]:
            print(kwargs["authorization_prompt_message"].format(url="https://accounts.example/authorize"))
        return self.credentials


def test_android_loopback_authorization_writes_mode_600_without_secret_output(capsys):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        client = root / "desktop-client.json"
        token = root / "private" / "drive-token.json"
        client.write_text("{}", encoding="utf-8")
        sensitive_value = "sensitive" + "-runtime-material"
        serialized = json.dumps({"scopes": [DRIVE_READONLY_SCOPE], "refresh_token": sensitive_value})
        credentials = FakeCredentials([DRIVE_READONLY_SCOPE], serialized)
        flow = FakeFlow(credentials)

        written = authorize_desktop_client(
            client_file=client,
            token_file=token,
            open_browser=False,
            flow_factory=lambda client_path, scopes: flow,
        )
        output = capsys.readouterr()

        assert written == token
        assert token.read_text(encoding="utf-8") == serialized
        assert stat.S_IMODE(token.stat().st_mode) == 0o600
        assert stat.S_IMODE(token.parent.stat().st_mode) == 0o700
        assert sensitive_value not in output.out
        assert sensitive_value not in output.err
        assert "https://accounts.example/authorize" in output.out
        assert flow.run_kwargs["host"] == "127.0.0.1"
        assert flow.run_kwargs["port"] == 0
        assert flow.run_kwargs["open_browser"] is False
        assert flow.run_kwargs["authorization_prompt_message"] == AUTHORIZATION_PROMPT
        assert flow.run_kwargs["access_type"] == "offline"
        assert flow.run_kwargs["prompt"] == "consent"


def test_repository_token_destination_is_rejected_before_flow_runs():
    with tempfile.TemporaryDirectory() as temporary:
        client = Path(temporary) / "desktop-client.json"
        client.write_text("{}", encoding="utf-8")
        with pytest.raises(CredentialSafetyError, match="must be outside"):
            authorize_desktop_client(
                client_file=client,
                token_file=Path(__file__).resolve().parents[1] / "unsafe-token.json",
                open_browser=False,
                flow_factory=lambda client_path, scopes: pytest.fail("flow must not start"),
            )


def test_relative_token_destination_is_rejected():
    with tempfile.TemporaryDirectory() as temporary:
        client = Path(temporary) / "desktop-client.json"
        client.write_text("{}", encoding="utf-8")
        with pytest.raises(CredentialSafetyError, match="absolute path"):
            authorize_desktop_client(
                client_file=client,
                token_file=Path("drive-token.json"),
                open_browser=False,
                flow_factory=lambda client_path, scopes: pytest.fail("flow must not start"),
            )


def test_broader_authorization_scope_is_rejected_without_token_write():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        client = root / "desktop-client.json"
        token = root / "drive-token.json"
        client.write_text("{}", encoding="utf-8")
        credentials = FakeCredentials(
            [DRIVE_READONLY_SCOPE, "https://www.googleapis.com/auth/drive"],
            json.dumps({"scopes": [DRIVE_READONLY_SCOPE]}),
        )
        with pytest.raises(CredentialSafetyError, match="broader scopes"):
            authorize_desktop_client(
                client_file=client,
                token_file=token,
                open_browser=False,
                flow_factory=lambda client_path, scopes: FakeFlow(credentials),
            )
        assert not token.exists()


def test_broader_runtime_token_scope_is_rejected_before_google_client_loading():
    with tempfile.TemporaryDirectory() as temporary:
        token = Path(temporary) / "drive-token.json"
        token.write_text(
            json.dumps({"scopes": [DRIVE_READONLY_SCOPE, "https://www.googleapis.com/auth/drive"]}),
            encoding="utf-8",
        )
        os.chmod(token, 0o600)
        with pytest.raises(CredentialSafetyError, match="broader scopes"):
            validate_authorized_user_token_file(token)

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setenv("CLAIRE_CRB_GOOGLE_TOKEN_FILE", str(token))
            monkeypatch.delenv("CLAIRE_CRB_GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
            with pytest.raises(GoogleDriveCredentialError, match="broader scopes"):
                load_readonly_credentials()
