from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_crb.google_drive import GOOGLE_DOC_MIME, GoogleDriveCredentialError, GoogleDriveReadOnlyConnector
from claire_crb.pipeline import CRBPipeline


class FakeRequest:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class FakeFiles:
    def __init__(self):
        self.list_calls = []
        self.get_calls = []
        self.media_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        if kwargs.get("pageToken") is None:
            return FakeRequest({"files": [{"id": "one", "name": "First.txt", "mimeType": "text/plain"}], "nextPageToken": "page-2"})
        return FakeRequest({"files": [{"id": "two", "name": "Second", "mimeType": GOOGLE_DOC_MIME}]})

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        file_id = kwargs["fileId"]
        if file_id == "parent":
            return FakeRequest({"id": "parent", "name": "Evidence", "mimeType": "application/vnd.google-apps.folder"})
        return FakeRequest({
            "id": file_id,
            "name": "Costa Interview",
            "mimeType": "text/plain",
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
            "parents": ["parent"],
            "createdTime": "2026-01-01T00:00:00Z",
            "modifiedTime": "2026-02-01T00:00:00Z",
        })

    def get_media(self, **kwargs):
        self.media_calls.append(("get", kwargs))
        return FakeRequest(b"George Costa discussed the evidence timeline.")

    def export_media(self, **kwargs):
        self.media_calls.append(("export", kwargs))
        return FakeRequest(b"A Google Doc mentioning George Costa and the filing.")


class FakeService:
    def __init__(self):
        self.files_api = FakeFiles()

    def files(self):
        return self.files_api


def make_store(root: Path) -> AREStore:
    return AREStore(AREConfig(root=root, hmac_key=b"crb-test-key"))


def test_drive_list_paginates_and_remains_bounded():
    service = FakeService()
    connector = GoogleDriveReadOnlyConnector(service)
    files = list(connector.list_files(folder_id="bounded-folder", name_contains="Costa", page_size=1))
    assert [item["id"] for item in files] == ["one", "two"]
    assert len(service.files_api.list_calls) == 2
    assert all("'bounded-folder' in parents" in call["q"] for call in service.files_api.list_calls)
    assert all("trashed = false" in call["q"] for call in service.files_api.list_calls)


def test_drive_download_and_google_doc_export_preserve_identity_and_path():
    service = FakeService()
    connector = GoogleDriveReadOnlyConnector(service)
    ordinary = connector.acquire("drive-ordinary")
    native = connector.acquire({
        "id": "drive-doc",
        "name": "Native Notes",
        "mimeType": GOOGLE_DOC_MIME,
        "webViewLink": "https://docs.google.com/document/d/drive-doc/edit",
    })
    assert ordinary.provider_document_id == "drive-ordinary"
    assert ordinary.original_path == "/Evidence/Costa Interview"
    assert ordinary.content_hash == hashlib.sha256(ordinary.content).hexdigest()
    assert native.filename == "Native Notes.txt"
    assert ("export", {"fileId": "drive-doc", "mimeType": "text/plain"}) in service.files_api.media_calls


def test_vertical_slice_is_idempotent_and_returns_provenance():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        connector = GoogleDriveReadOnlyConnector(FakeService())
        document = connector.acquire("drive-costa-1")
        store = make_store(root / "are")
        pipeline = CRBPipeline(store, lane="legal")
        try:
            first = pipeline.ingest_document(document)
            second = pipeline.ingest_document(document)
            results = pipeline.search("George Costa")
            verification = store.verify()
        finally:
            store.stop()

        assert first["ingested_chunks"] == 1
        assert second["ingested_chunks"] == 0
        assert second["deduplicated_chunks"] == 1
        assert verification["valid"] is True
        assert len(results) == 1
        result = results[0]
        assert result["query"] == "George Costa"
        assert "George Costa" in result["matched_excerpt"]
        assert result["provider"] == "google_drive"
        assert result["provider_document_id"] == "drive-costa-1"
        assert result["original_uri"].startswith("https://drive.google.com/")
        assert len(result["source_content_hash"]) == 64
        assert len(result["parser_chunk_hash"]) == 64
        assert result["extraction_method"] == "native_text"
        assert len(result["are_truth_hash"]) == 64


def test_credentials_require_exactly_one_external_file():
    from claire_crb.google_drive import load_readonly_credentials

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(GoogleDriveCredentialError, match="Set exactly one"):
            load_readonly_credentials()


@pytest.mark.skipif(
    not os.environ.get("CLAIRE_CRB_E2E_DRIVE_DOCUMENT_ID"),
    reason="real Drive E2E requires explicit bounded document ID and external credentials",
)
def test_real_drive_george_costa_end_to_end():
    """Credential-gated proof; never traverses Drive and never writes to Drive."""

    document_id = os.environ["CLAIRE_CRB_E2E_DRIVE_DOCUMENT_ID"]
    connector = GoogleDriveReadOnlyConnector.from_environment()
    document = connector.acquire(document_id)
    with tempfile.TemporaryDirectory() as temporary:
        store = make_store(Path(temporary) / "are")
        try:
            pipeline = CRBPipeline(store, lane="legal")
            pipeline.ingest_document(document)
            results = pipeline.search("George Costa")
            assert results, "The bounded real Drive document did not contain a searchable George Costa match"
            assert store.verify()["valid"] is True
            print(json.dumps(results[0], ensure_ascii=False, sort_keys=True))
        finally:
            store.stop()
