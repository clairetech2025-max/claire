from __future__ import annotations

import hashlib
import io
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any, Iterator

from .contracts import NormalizedDocument
from .oauth_security import (
    DRIVE_READONLY_SCOPE,
    CredentialSafetyError,
    external_credential_path,
    require_exact_credential_scopes,
    validate_authorized_user_token_file,
)


GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_EXPORTS = {
    GOOGLE_DOC_MIME: ("text/plain", ".txt"),
}
MIME_EXTENSIONS = {
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
    "application/json": ".json",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.oasis.opendocument.text": ".odt",
}


class GoogleDriveCredentialError(RuntimeError):
    pass


def load_readonly_credentials() -> Any:
    """Load Google credentials from an external file without logging secret material."""

    token_file = os.environ.get("CLAIRE_CRB_GOOGLE_TOKEN_FILE", "").strip()
    service_account_file = os.environ.get("CLAIRE_CRB_GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if bool(token_file) == bool(service_account_file):
        raise GoogleDriveCredentialError(
            "Set exactly one of CLAIRE_CRB_GOOGLE_TOKEN_FILE or "
            "CLAIRE_CRB_GOOGLE_SERVICE_ACCOUNT_FILE to an external credential JSON file."
        )
    try:
        if token_file:
            safe_token = validate_authorized_user_token_file(token_file)
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            credentials = Credentials.from_authorized_user_file(str(safe_token), [DRIVE_READONLY_SCOPE])
            require_exact_credential_scopes(credentials)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                require_exact_credential_scopes(credentials)
            if not credentials.valid:
                raise GoogleDriveCredentialError("The configured Google OAuth token is not valid or refreshable.")
            return credentials

        from google.oauth2 import service_account

        safe_service_account = external_credential_path(
            service_account_file,
            label="Google service-account file",
            must_exist=True,
        )
        credentials = service_account.Credentials.from_service_account_file(
            str(safe_service_account),
            scopes=[DRIVE_READONLY_SCOPE],
        )
        require_exact_credential_scopes(credentials)
        return credentials
    except (GoogleDriveCredentialError, CredentialSafetyError) as exc:
        if isinstance(exc, GoogleDriveCredentialError):
            raise
        raise GoogleDriveCredentialError(str(exc)) from exc
    except ImportError as exc:
        raise GoogleDriveCredentialError(
            "Google Drive client dependencies are not installed; install the project 'crb' optional dependencies."
        ) from exc
    except Exception as exc:
        raise GoogleDriveCredentialError(f"Google credential loading failed: {type(exc).__name__}") from exc


def build_drive_service(credentials: Any | None = None) -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise GoogleDriveCredentialError(
            "Google Drive client dependencies are not installed; install the project 'crb' optional dependencies."
        ) from exc
    return build("drive", "v3", credentials=credentials or load_readonly_credentials(), cache_discovery=False)


class GoogleDriveReadOnlyConnector:
    """Bounded Google Drive acquisition using only files.list/get/get_media/export."""

    FILE_FIELDS = (
        "id,name,mimeType,createdTime,modifiedTime,webViewLink,parents,size,md5Checksum,trashed"
    )

    def __init__(self, service: Any) -> None:
        self.service = service
        self._metadata_cache: dict[str, dict[str, Any]] = {}

    @classmethod
    def from_environment(cls) -> "GoogleDriveReadOnlyConnector":
        return cls(build_drive_service())

    def list_files(
        self,
        *,
        folder_id: str,
        name_contains: str = "",
        page_size: int = 100,
        max_files: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        if not str(folder_id or "").strip():
            raise ValueError("folder_id is required to keep Drive acquisition bounded")
        escaped = str(name_contains or "").replace("'", "\\'")
        query = f"'{folder_id}' in parents and trashed = false"
        if escaped:
            query += f" and name contains '{escaped}'"
        token = None
        emitted = 0
        while True:
            response = self.service.files().list(
                q=query,
                spaces="drive",
                fields=f"nextPageToken,files({self.FILE_FIELDS})",
                pageSize=max(1, min(int(page_size), 1000)),
                pageToken=token,
                orderBy="modifiedTime desc",
            ).execute()
            for item in response.get("files", []):
                if item.get("mimeType") == GOOGLE_FOLDER_MIME:
                    continue
                yield dict(item)
                emitted += 1
                if max_files is not None and emitted >= max(0, int(max_files)):
                    return
            token = response.get("nextPageToken")
            if not token:
                return

    def discover_candidates(
        self,
        *,
        exact_phrase: str,
        folder_id: str = "",
        allow_corpus_wide: bool = False,
        max_candidates: int = 10,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        phrase = str(exact_phrase or "").strip()
        if not phrase:
            raise ValueError("exact_phrase is required")
        folder = str(folder_id or "").strip()
        if not folder and not allow_corpus_wide:
            raise ValueError("Corpus-wide candidate discovery requires explicit allow_corpus_wide=True")
        cap = int(max_candidates)
        if cap < 1 or cap > 100:
            raise ValueError("max_candidates must be between 1 and 100")
        escaped_phrase = self._escape_query_value(f'"{phrase}"')
        clauses = [f"fullText contains '{escaped_phrase}'", "trashed = false"]
        if folder:
            clauses.insert(0, f"'{self._escape_query_value(folder)}' in parents")
        query = " and ".join(clauses)
        candidates: list[dict[str, Any]] = []
        token = None
        while len(candidates) < cap:
            response = self.service.files().list(
                q=query,
                spaces="drive",
                corpora="user",
                fields=f"nextPageToken,incompleteSearch,files({self.FILE_FIELDS})",
                pageSize=max(1, min(int(page_size), cap - len(candidates), 1000)),
                pageToken=token,
                orderBy="modifiedTime desc",
            ).execute()
            for item in response.get("files", []):
                if item.get("trashed") is True or item.get("mimeType") == GOOGLE_FOLDER_MIME:
                    continue
                candidates.append(dict(item))
                if len(candidates) >= cap:
                    break
            token = response.get("nextPageToken")
            if not token:
                break
        return candidates

    @staticmethod
    def _escape_query_value(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace("'", "\\'")

    def get_metadata(self, document_id: str) -> dict[str, Any]:
        if document_id not in self._metadata_cache:
            self._metadata_cache[document_id] = dict(
                self.service.files().get(fileId=document_id, fields=self.FILE_FIELDS).execute()
            )
        return dict(self._metadata_cache[document_id])

    def acquire(self, metadata_or_id: dict[str, Any] | str) -> NormalizedDocument:
        metadata = (
            self.get_metadata(metadata_or_id)
            if isinstance(metadata_or_id, str)
            else dict(metadata_or_id)
        )
        document_id = str(metadata.get("id") or "")
        if not document_id:
            raise ValueError("Drive document metadata is missing id")
        mime_type = str(metadata.get("mimeType") or "application/octet-stream")
        if mime_type in GOOGLE_EXPORTS:
            export_mime, extension = GOOGLE_EXPORTS[mime_type]
            request = self.service.files().export_media(fileId=document_id, mimeType=export_mime)
        elif mime_type.startswith("application/vnd.google-apps."):
            raise ValueError(f"Unsupported native Google file type for this slice: {mime_type}")
        else:
            extension = (
                PurePosixPath(str(metadata.get("name") or "evidence")).suffix
                or MIME_EXTENSIONS.get(mime_type)
                or mimetypes.guess_extension(mime_type, strict=False)
                or ".bin"
            )
            request = self.service.files().get_media(fileId=document_id)
        content = self._read_media(request)
        name = str(metadata.get("name") or document_id)
        filename = name if name.lower().endswith(extension.lower()) else f"{name}{extension}"
        acquired_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return NormalizedDocument(
            provider="google_drive",
            provider_document_id=document_id,
            original_uri=str(metadata.get("webViewLink") or f"https://drive.google.com/open?id={document_id}"),
            original_path=self._resolve_path(metadata),
            title=name,
            filename=filename,
            mime_type=mime_type,
            staged_extension=extension,
            content=content,
            content_hash=hashlib.sha256(content).hexdigest(),
            created_time=str(metadata.get("createdTime") or ""),
            modified_time=str(metadata.get("modifiedTime") or ""),
            acquired_at=acquired_at,
            provider_metadata={
                "size": metadata.get("size"),
                "md5_checksum": metadata.get("md5Checksum"),
                "parent_ids": list(metadata.get("parents") or []),
            },
        )

    def _resolve_path(self, metadata: dict[str, Any]) -> str:
        names = [str(metadata.get("name") or metadata.get("id") or "document")]
        seen: set[str] = set()
        parents = list(metadata.get("parents") or [])
        while parents:
            parent_id = str(parents[0])
            if not parent_id or parent_id in seen:
                break
            seen.add(parent_id)
            try:
                parent = self.get_metadata(parent_id)
            except Exception:
                break
            names.append(str(parent.get("name") or parent_id))
            parents = list(parent.get("parents") or [])
        return "/" + "/".join(reversed(names))

    @staticmethod
    def _read_media(request: Any) -> bytes:
        try:
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError:
            result = request.execute()
            return result.encode("utf-8") if isinstance(result, str) else bytes(result)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()
