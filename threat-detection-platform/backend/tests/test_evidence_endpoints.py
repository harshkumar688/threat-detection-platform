"""
Evidence API Endpoint Tests (HTTP level)

Verifies the evidence router is correctly wired to the real EvidenceService:
- Listing evidence for an incident reflects actual captured records
- Downloading evidence returns real file bytes with correct MIME type
- Unauthenticated requests are rejected
- Nonexistent evidence returns 404, not a crash
"""

import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport
from uuid import uuid4

from app.main import app
from app.core.security import create_access_token
from app.api.v1.evidence import _service as evidence_service


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def operator_token():
    return create_access_token(subject="op-001", role="operator", extra_claims={"email": "op@test.com"})


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_frame():
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[50:150, 50:150] = (0, 0, 255)
    return frame


class TestEvidenceRequiresAuth:
    @pytest.mark.asyncio
    async def test_list_requires_auth(self, client):
        resp = await client.get(f"/api/v1/evidence/{uuid4()}")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_download_requires_auth(self, client):
        resp = await client.get(f"/api/v1/evidence/file/{uuid4()}")
        assert resp.status_code == 401


class TestListEvidence:
    @pytest.mark.asyncio
    async def test_empty_incident_returns_no_items(self, client, operator_token):
        incident_id = uuid4()
        resp = await client.get(f"/api/v1/evidence/{incident_id}", headers=auth_header(operator_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_reflects_real_captured_snapshot(self, client, operator_token, sample_frame):
        incident_id = uuid4()

        # Capture evidence directly through the real service (as the detection
        # pipeline would when an incident is confirmed)
        record = await evidence_service.capture_snapshot(
            frame=sample_frame,
            incident_id=incident_id,
            camera_id="cam-lobby",
            frame_number=42,
        )

        resp = await client.get(f"/api/v1/evidence/{incident_id}", headers=auth_header(operator_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(record.id)
        assert data["items"][0]["evidence_type"] == "snapshot"
        assert data["items"][0]["camera_id"] == "cam-lobby"
        assert data["items"][0]["mime_type"] == "image/jpeg"
        assert data["items"][0]["file_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_invalid_incident_id_returns_404(self, client, operator_token):
        resp = await client.get("/api/v1/evidence/not-a-uuid", headers=auth_header(operator_token))
        assert resp.status_code == 404


class TestDownloadEvidence:
    @pytest.mark.asyncio
    async def test_download_real_snapshot_returns_jpeg_bytes(self, client, operator_token, sample_frame):
        incident_id = uuid4()
        record = await evidence_service.capture_snapshot(
            frame=sample_frame,
            incident_id=incident_id,
            camera_id="cam-01",
        )

        resp = await client.get(f"/api/v1/evidence/file/{record.id}", headers=auth_header(operator_token))
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        # Valid JPEG magic bytes
        assert resp.content[:2] == b"\xff\xd8"
        assert len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_download_nonexistent_returns_404(self, client, operator_token):
        resp = await client.get(f"/api/v1/evidence/file/{uuid4()}", headers=auth_header(operator_token))
        assert resp.status_code == 404
        data = resp.json()
        assert data["status"] == "error"

    @pytest.mark.asyncio
    async def test_download_invalid_uuid_returns_404_not_500(self, client, operator_token):
        resp = await client.get("/api/v1/evidence/file/not-a-uuid", headers=auth_header(operator_token))
        assert resp.status_code == 404
