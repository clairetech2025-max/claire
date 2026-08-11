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


class CandidateFiles(FakeFiles):
    def __init__(self, pages):
        super().__init__()
        self.pages = list(pages)

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return FakeRequest(self.pages.pop(0))


class CandidateService(FakeService):
    def __init__(self, pages):
        self.files_api = CandidateFiles(pages)


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


def test_candidate_discovery_is_folder_bounded_paginated_capped_and_excludes_trashed():
    service = CandidateService([
        {
            "files": [
                {"id": "trashed", "name": "Discard", "mimeType": "text/plain", "trashed": True},
                {"id": "one", "name": "First", "mimeType": "text/plain", "trashed": False},
            ],
            "nextPageToken": "page-2",
        },
        {
            "files": [
                {"id": "two", "name": "Second", "mimeType": GOOGLE_DOC_MIME, "trashed": False},
                {"id": "three", "name": "Third", "mimeType": "text/plain", "trashed": False},
            ]
        },
    ])
    connector = GoogleDriveReadOnlyConnector(service)
    candidates = connector.discover_candidates(
        exact_phrase="George Costa",
        folder_id="evidence-folder",
        max_candidates=2,
        page_size=20,
    )
    assert [item["id"] for item in candidates] == ["one", "two"]
    assert len(service.files_api.list_calls) == 2
    first_call = service.files_api.list_calls[0]
    assert "'evidence-folder' in parents" in first_call["q"]
    assert "fullText contains '\"George Costa\"'" in first_call["q"]
    assert "trashed = false" in first_call["q"]
    assert first_call["corpora"] == "user"
    assert service.files_api.list_calls[1]["pageSize"] == 1


def test_corpus_wide_candidate_discovery_requires_explicit_approval():
    connector = GoogleDriveReadOnlyConnector(CandidateService([]))
    with pytest.raises(ValueError, match="explicit allow_corpus_wide=True"):
        connector.discover_candidates(exact_phrase="George Costa", max_candidates=5)


def test_corpus_wide_candidate_discovery_is_capped_when_explicitly_approved():
    service = CandidateService([{
        "files": [
            {"id": "one", "mimeType": "text/plain", "trashed": False},
            {"id": "two", "mimeType": "text/plain", "trashed": False},
            {"id": "three", "mimeType": "text/plain", "trashed": False},
        ],
        "nextPageToken": "must-not-be-followed",
    }])
    connector = GoogleDriveReadOnlyConnector(service)
    candidates = connector.discover_candidates(
        exact_phrase="George Costa",
        allow_corpus_wide=True,
        max_candidates=2,
    )
    assert [item["id"] for item in candidates] == ["one", "two"]
    assert len(service.files_api.list_calls) == 1


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
    not (
        os.environ.get("CLAIRE_CRB_E2E_DRIVE_DOCUMENT_ID")
        or os.environ.get("CLAIRE_CRB_E2E_DRIVE_FOLDER_ID")
        or os.environ.get("CLAIRE_CRB_E2E_ALLOW_CORPUS_WIDE", "").strip().lower() in {"1", "true", "yes"}
    ),
    reason="real Drive E2E requires an explicit document, folder, or approved capped corpus search",
)
def test_real_drive_george_costa_end_to_end():
    """Credential-gated proof; candidate discovery is capped and Drive remains read-only."""

    connector = GoogleDriveReadOnlyConnector.from_environment()
    document_id = os.environ.get("CLAIRE_CRB_E2E_DRIVE_DOCUMENT_ID", "").strip()
    if document_id:
        candidates = [connector.get_metadata(document_id)]
    else:
        candidates = connector.discover_candidates(
            exact_phrase="George Costa",
            folder_id=os.environ.get("CLAIRE_CRB_E2E_DRIVE_FOLDER_ID", "").strip(),
            allow_corpus_wide=os.environ.get("CLAIRE_CRB_E2E_ALLOW_CORPUS_WIDE", "").strip().lower() in {"1", "true", "yes"},
            max_candidates=10,
        )
    assert candidates, "Drive candidate discovery returned no bounded George Costa candidates"
    with tempfile.TemporaryDirectory() as temporary:
        store = make_store(Path(temporary) / "are")
        try:
            pipeline = CRBPipeline(store, lane="legal")
            results = []
            for candidate in candidates:
                pipeline.ingest_document(connector.acquire(candidate))
                results = pipeline.search("George Costa")
                if results:
                    break
            assert results, "The bounded real Drive document did not contain a searchable George Costa match"
            assert store.verify()["valid"] is True
            print(json.dumps(results[0], ensure_ascii=False, sort_keys=True))
        finally:
            store.stop()
