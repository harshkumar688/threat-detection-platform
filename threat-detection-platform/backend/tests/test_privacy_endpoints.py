"""
Privacy & Evidence Access Restriction Endpoint Tests (HTTP level)

Verifies:
- Viewers can list evidence metadata but CANNOT download the file
- Operators and admins CAN download evidence
- Denied download attempts are recorded in the evidence audit log
- Only admins can view the evidence audit log
- /evidence/privacy/status is reachable by any authenticated user and
  reports the real configured mode + documented limitations
"""

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from uuid import uuid4

from app.main import app
from app.core.security import create_access_token
from app.api.v1.evidence import _service as evidence_service, _audit_log


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def clear_audit_log():
    _audit_log.clear()
    yield
    _audit_log.clear()


@pytest.fixture
def admin_token():
    return create_access_token(subject="admin-001", role="admin", extra_claims={"email": "admin@test.com"})


@pytest.fixture
def operator_token():
    return create_access_token(subject="op-001", role="operator", extra_claims={"email": "op@test.com"})


@pytest.fixture
def viewer_token():
    return create_access_token(subject="viewer-001", role="viewer", extra_claims={"email": "viewer@test.com"})


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_frame():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[50:150, 50:150] = (10, 20, 200)
    return frame


class TestEvidenceDownloadAccessRestriction:
    @pytest.mark.asyncio
    async def test_viewer_can_list_evidence(self, client, viewer_token, sample_frame):
        incident_id = uuid4()
        await evidence_service.capture_snapshot(frame=sample_frame, incident_id=incident_id, camera_id="cam-01")

        resp = await client.get(f"/api/v1/evidence/{incident_id}", headers=auth_header(viewer_token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_viewer_cannot_download_evidence_file(self, client, viewer_token, sample_frame):
        incident_id = uuid4()
        record = await evidence_service.capture_snapshot(frame=sample_frame, incident_id=incident_id)

        resp = await client.get(f"/api/v1/evidence/file/{record.id}", headers=auth_header(viewer_token))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_operator_can_download_evidence_file(self, client, operator_token, sample_frame):
        incident_id = uuid4()
        record = await evidence_service.capture_snapshot(frame=sample_frame, incident_id=incident_id)

        resp = await client.get(f"/api/v1/evidence/file/{record.id}", headers=auth_header(operator_token))
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_admin_can_download_evidence_file(self, client, admin_token, sample_frame):
        incident_id = uuid4()
        record = await evidence_service.capture_snapshot(frame=sample_frame, incident_id=incident_id)

        resp = await client.get(f"/api/v1/evidence/file/{record.id}", headers=auth_header(admin_token))
        assert resp.status_code == 200


class TestEvidenceAuditLogEndpoint:
    @pytest.mark.asyncio
    async def test_denied_download_is_audited(self, client, viewer_token, sample_frame):
        incident_id = uuid4()
        record = await evidence_service.capture_snapshot(frame=sample_frame, incident_id=incident_id)

        await client.get(f"/api/v1/evidence/file/{record.id}", headers=auth_header(viewer_token))

        entries = _audit_log.get_entries(evidence_id=record.id)
        actions = [e.action.value for e in entries]
        assert "access_denied" in actions

    @pytest.mark.asyncio
    async def test_successful_download_is_audited(self, client, operator_token, sample_frame):
        incident_id = uuid4()
        record = await evidence_service.capture_snapshot(frame=sample_frame, incident_id=incident_id)

        await client.get(f"/api/v1/evidence/file/{record.id}", headers=auth_header(operator_token))

        entries = _audit_log.get_entries(evidence_id=record.id)
        actions = [e.action.value for e in entries]
        assert "file_downloaded" in actions

    @pytest.mark.asyncio
    async def test_list_view_is_audited(self, client, viewer_token, sample_frame):
        incident_id = uuid4()
        await evidence_service.capture_snapshot(frame=sample_frame, incident_id=incident_id)

        await client.get(f"/api/v1/evidence/{incident_id}", headers=auth_header(viewer_token))

        entries = _audit_log.get_entries(incident_id=incident_id)
        actions = [e.action.value for e in entries]
        assert "list_viewed" in actions

    @pytest.mark.asyncio
    async def test_admin_can_view_audit_log(self, client, admin_token, operator_token, sample_frame):
        incident_id = uuid4()
        record = await evidence_service.capture_snapshot(frame=sample_frame, incident_id=incident_id)
        await client.get(f"/api/v1/evidence/file/{record.id}", headers=auth_header(operator_token))

        resp = await client.get("/api/v1/evidence/audit/log", headers=auth_header(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_operator_cannot_view_audit_log(self, client, operator_token):
        resp = await client.get("/api/v1/evidence/audit/log", headers=auth_header(operator_token))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_view_audit_log(self, client, viewer_token):
        resp = await client.get("/api/v1/evidence/audit/log", headers=auth_header(viewer_token))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_audit_log_requires_auth(self, client):
        resp = await client.get("/api/v1/evidence/audit/log")
        assert resp.status_code == 401


class TestPrivacyStatusEndpoint:
    @pytest.mark.asyncio
    async def test_privacy_status_reachable_by_any_authenticated_role(self, client, viewer_token):
        resp = await client.get("/api/v1/evidence/privacy/status", headers=auth_header(viewer_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] in ("off", "face_blur", "face_pixelate")
        assert "limitations" in data
        assert len(data["limitations"]) > 0

    @pytest.mark.asyncio
    async def test_privacy_status_requires_auth(self, client):
        resp = await client.get("/api/v1/evidence/privacy/status")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_privacy_status_documents_no_recognition(self, client, admin_token):
        resp = await client.get("/api/v1/evidence/privacy/status", headers=auth_header(admin_token))
        data = resp.json()
        combined = " ".join(data["limitations"]).lower()
        assert "recognition" in combined or "identity" in combined
