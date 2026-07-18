from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import claire_vde.api as api_module
from claire_are.config import AREConfig
from claire_are.core import AREStore
from claire_vde.security import VentureSecurity
from claire_vde.storage import VentureRepository


def make_store(root: Path) -> AREStore:
    return AREStore(AREConfig(root=root, hmac_key=b"security-test-key", max_segment_records=2))


def make_auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_payload() -> dict[str, object]:
    return {
        "title": "Security test evidence",
        "text": "Security controls should protect this route.",
        "source": "security_test",
        "collector": "test",
        "plane": "regulatory_pressure",
        "value": 0.2,
        "precision": 1.0,
        "confidence": 0.8,
        "provenance_url": "https://example.test/security",
        "entity_refs": [],
        "metadata": {},
    }


def configure_test_security(repo: VentureRepository) -> VentureSecurity:
    return VentureSecurity(
        repo,
        read_token="read-token",
        write_token="write-token",
        admin_token="admin-token",
        rate_limit_per_minute=1,
    )


def test_health_route_remains_public():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        old_store = api_module.store
        old_repo = api_module.repository
        old_security = api_module.security
        api_module.store = store
        api_module.repository = repo
        api_module.security = configure_test_security(repo)
        try:
            client = TestClient(api_module.app)
            response = client.get("/v1/venture/health")
            assert response.status_code == 200
        finally:
            store.stop()
            api_module.store = old_store
            api_module.repository = old_repo
            api_module.security = old_security


def test_missing_token_is_rejected_and_audited():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        old_store = api_module.store
        old_repo = api_module.repository
        old_security = api_module.security
        api_module.store = store
        api_module.repository = repo
        api_module.security = configure_test_security(repo)
        try:
            client = TestClient(api_module.app)
            response = client.post("/v1/venture/evidence/admit", json=make_payload())
            assert response.status_code == 401
            with repo.connect() as conn:
                audit = conn.execute("SELECT decision, reason, client_key FROM api_request_audit ORDER BY created_at DESC LIMIT 1").fetchone()
            assert audit["decision"] == "denied"
            assert audit["reason"] == "missing_token"
            assert audit["client_key"]
            assert "write-token" not in audit["client_key"]
        finally:
            store.stop()
            api_module.store = old_store
            api_module.repository = old_repo
            api_module.security = old_security


def test_invalid_token_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        old_store = api_module.store
        old_repo = api_module.repository
        old_security = api_module.security
        api_module.store = store
        api_module.repository = repo
        api_module.security = configure_test_security(repo)
        try:
            client = TestClient(api_module.app)
            response = client.post("/v1/venture/evidence/admit", json=make_payload(), headers=make_auth_headers("bad-token"))
            assert response.status_code == 403
        finally:
            store.stop()
            api_module.store = old_store
            api_module.repository = old_repo
            api_module.security = old_security


def test_insufficient_permission_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        old_store = api_module.store
        old_repo = api_module.repository
        old_security = api_module.security
        api_module.store = store
        api_module.repository = repo
        api_module.security = configure_test_security(repo)
        try:
            client = TestClient(api_module.app)
            response = client.post("/v1/venture/evidence/admit", json=make_payload(), headers=make_auth_headers("read-token"))
            assert response.status_code == 403
            with repo.connect() as conn:
                audit = conn.execute("SELECT reason FROM api_request_audit ORDER BY created_at DESC LIMIT 1").fetchone()
            assert audit["reason"].startswith("insufficient_permission")
        finally:
            store.stop()
            api_module.store = old_store
            api_module.repository = old_repo
            api_module.security = old_security


def test_valid_token_is_accepted():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        old_store = api_module.store
        old_repo = api_module.repository
        old_security = api_module.security
        api_module.store = store
        api_module.repository = repo
        api_module.security = configure_test_security(repo)
        try:
            client = TestClient(api_module.app)
            response = client.post("/v1/venture/evidence/admit", json=make_payload(), headers=make_auth_headers("write-token"))
            assert response.status_code == 200
        finally:
            store.stop()
            api_module.store = old_store
            api_module.repository = old_repo
            api_module.security = old_security


def test_rate_limit_exceeded_returns_429():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        store = make_store(root / "are")
        repo = VentureRepository(root / "venture.sqlite")
        old_store = api_module.store
        old_repo = api_module.repository
        old_security = api_module.security
        api_module.store = store
        api_module.repository = repo
        api_module.security = configure_test_security(repo)
        try:
            client = TestClient(api_module.app)
            first = client.post("/v1/venture/evidence/admit", json=make_payload(), headers=make_auth_headers("write-token"))
            second = client.post("/v1/venture/evidence/admit", json=make_payload(), headers=make_auth_headers("write-token"))
            assert first.status_code == 200
            assert second.status_code == 429
        finally:
            store.stop()
            api_module.store = old_store
            api_module.repository = old_repo
            api_module.security = old_security
