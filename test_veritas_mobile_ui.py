from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import claire_gui


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(claire_gui, "VERITAS_MOBILE_STATE_DIR", str(tmp_path / "veritas_mobile"))
    return TestClient(claire_gui.app)


def create_case(client: TestClient, name: str = "Mobile Smoke Case") -> str:
    response = client.post("/veritas-mobile/api/cases", json={"name": name})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "created"
    return payload["case"]["case_id"]


def upload_text(client: TestClient, case_id: str, filename: str = "notice.txt") -> dict:
    text = (
        "On 2013-03-15 Sean James cited CCR 4331 in a Claire Systems notice. "
        "Patrick Tuck reviewed the evidence before the permit was revoked."
    )
    response = client.post(
        f"/veritas-mobile/api/cases/{case_id}/upload",
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "processed"
    return payload


def upload_binary(client: TestClient, case_id: str, filename: str, content: bytes, content_type: str) -> dict:
    response = client.post(
        f"/veritas-mobile/api/cases/{case_id}/upload",
        files={"file": (filename, content, content_type)},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "processed"
    return payload


def make_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length 91 >> stream\n"
        b"BT /F1 24 Tf 72 720 Td (On 2013-03-15 Sean James cited CCR 4331 in a Claire Systems notice.) Tj ET\n"
        b"endstream endobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000119 00000 n \n0000000244 00000 n \n0000000384 00000 n \n"
        b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n455\n%%EOF\n"
    )


def test_mobile_home_loads_with_android_first_controls(client):
    response = client.get("/veritas-mobile")

    assert response.status_code == 200
    html = response.text
    assert '<meta name="viewport"' in html
    assert "New Case" in html
    assert "Upload Evidence" in html
    assert "Home</button><button onclick=\"requireCase('case')\">Case" in html
    assert "min-height:52px" in html
    assert "Show Technical Details" in html
    assert "Docker" not in html
    assert "GitHub" not in html


def test_new_case_flow_and_case_dashboard(client):
    case_id = create_case(client, "Sean James Matter")

    response = client.get(f"/veritas-mobile/api/cases/{case_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Sean James Matter"
    assert payload["documents"] == []
    assert payload["what_changed"]["missing_document_warnings"]


def test_upload_success_extracts_plain_english_results(client):
    case_id = create_case(client)
    payload = upload_text(client, case_id)

    assert payload["source_record_created"] is True
    assert payload["dates_found"] >= 1
    assert payload["people_found"] >= 1
    assert payload["rules_found"] >= 1
    doc = payload["documents"][0]
    assert doc["source_doc_id"]
    assert len(doc["source_hash"]) == 64
    assert doc["are_event_sha"]


def test_docx_upload_extracts_plain_english_results(client, tmp_path):
    case_id = create_case(client)
    docx_path = tmp_path / "veritas_test.docx"
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"python-docx unavailable: {exc}")
    document = Document()
    document.add_paragraph(
        "On 2013-03-15 Sean James cited CCR 4331 in a Claire Systems notice. "
        "Patrick Tuck reviewed the evidence before the permit was revoked."
    )
    document.save(str(docx_path))
    payload = upload_binary(
        client,
        case_id,
        docx_path.name,
        docx_path.read_bytes(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert payload["source_record_created"] is True
    assert payload["documents"][0]["parser"] == "docx_extract"
    assert payload["dates_found"] >= 1
    assert payload["people_found"] >= 1


def test_pdf_upload_extracts_plain_english_results(client):
    case_id = create_case(client)
    payload = upload_binary(
        client,
        case_id,
        "veritas_test.pdf",
        make_pdf_bytes(),
        "application/pdf",
    )

    assert payload["source_record_created"] is True
    assert payload["documents"][0]["parser"] == "pdf_text_extract"
    assert payload["dates_found"] >= 1
    assert payload["people_found"] >= 1


def test_upload_failure_is_readable_and_not_success(client):
    case_id = create_case(client)
    response = client.post(
        f"/veritas-mobile/api/cases/{case_id}/upload",
        files={"file": ("photo.png", b"not-real-ocr", "image/png")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "unsupported"
    assert "not supported yet" in payload["detail"]


def test_document_detail_hides_technical_data_behind_details(client):
    case_id = create_case(client)
    upload_payload = upload_text(client, case_id)
    source_doc_id = upload_payload["documents"][0]["source_doc_id"]

    response = client.get(f"/veritas-mobile/api/cases/{case_id}/documents/{source_doc_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"].endswith("notice.txt")
    assert "Sean James" in payload["summary"]
    assert "2013-03-15" in payload["dates"]
    assert "CCR 4331" in payload["rules"]
    assert payload["source_hash"]


def test_natural_language_search_returns_source_linked_result(client):
    case_id = create_case(client)
    upload_text(client, case_id)

    response = client.post(
        f"/veritas-mobile/api/cases/{case_id}/search",
        json={"query": "Show every mention of Sean James."},
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert results
    assert results[0]["source_doc_id"]
    assert "Sean James" in results[0]["snippet"]


def test_timeline_source_linkage(client):
    case_id = create_case(client)
    upload_text(client, case_id)

    response = client.get(f"/veritas-mobile/api/cases/{case_id}/timeline")

    assert response.status_code == 200
    events = response.json()["events"]
    assert events
    assert events[0]["date"] == "2013-03-15"
    assert events[0]["source_doc_id"]
    assert events[0]["are_event_sha"]


def test_ask_veritas_uses_case_sources_and_not_demo_path(client):
    case_id = create_case(client)
    upload_text(client, case_id)

    response = client.post(
        f"/veritas-mobile/api/cases/{case_id}/ask",
        json={"question": "What is my strongest evidence?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["sources"]
    assert payload["boundary"]
    joined = f"{payload['answer']} {payload['boundary']}"
    assert "Simulated action only" not in joined
    assert "horseback ride" not in joined


def test_report_creation_saves_reopenable_source_referenced_report(client):
    case_id = create_case(client)
    upload_text(client, case_id)

    response = client.post(
        f"/veritas-mobile/api/cases/{case_id}/reports",
        json={"report_type": "document_index"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "saved"
    assert "Document Index" in payload["preview"]
    assert "source:" in payload["preview"]
    assert Path(payload["path"]).exists()


def test_unsupported_controls_are_not_advertised_as_working(client):
    response = client.get("/veritas-mobile")

    assert response.status_code == 200
    html = response.text
    assert 'accept=".txt,.md,.py,.pdf,.docx,.csv,.json,.jsonl"' in html
    assert "Take Photo" not in html
    assert "OCR" not in html


def test_private_case_isolation(client):
    first_case = create_case(client, "First Case")
    second_case = create_case(client, "Second Case")
    upload_text(client, first_case)

    response = client.post(
        f"/veritas-mobile/api/cases/{second_case}/search",
        json={"query": "Sean James"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []
