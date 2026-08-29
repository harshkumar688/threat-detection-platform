"""
Alert API Endpoint Tests (HTTP level)

Verifies the full chain: HTTP request → router → AlertService →
AlertRepository/NotificationDispatcher → real response, AND that
creating a confirmed incident through the real incidents API
automatically raises a real alert (not a fabricated one).
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.security import create_access_token
from app.api.v1.incidents import _repo as incident_repo
from app.api.v1.alerts import _repo as alert_repo
from app.api.v1.cameras import _camera_repo
from app.api.v1.locations import _location_repo


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def clear_stores():
    """Ensure clean incident + alert + camera + location stores before each test."""
    incident_repo.clear()
    alert_repo.clear()
    _camera_repo.clear()
    _location_repo.clear()
    yield
    incident_repo.clear()
    alert_repo.clear()
    _camera_repo.clear()
    _location_repo.clear()


@pytest.fixture
def operator_token():
    return create_access_token(subject="op-001", role="operator", extra_claims={"email": "op@test.com"})


@pytest.fixture
def admin_token():
    return create_access_token(subject="admin-001", role="admin", extra_claims={"email": "admin@test.com"})


@pytest.fixture
def viewer_token():
    return create_access_token(subject="viewer-001", role="viewer", extra_claims={"email": "viewer@test.com"})


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_camera(client, admin_token, name="cam-01"):
    """Register a real camera and return its assigned UUID."""
    resp = await client.post(
        "/api/v1/cameras/",
        headers=auth_header(admin_token),
        json={"name": name, "stream_url": f"rtsp://example.invalid/{name}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_incident(client, token, camera_id=None, threat_type="handgun", risk_level="HIGH", admin_token=None):
    """
    Create a real incident. If camera_id is not provided, registers a
    fresh camera first (incidents now require a real, registered camera).
    """
    if camera_id is None:
        admin = admin_token or create_access_token(
            subject="admin-001", role="admin", extra_claims={"email": "admin@test.com"}
        )
        camera_id = await _register_camera(client, admin, name=f"cam-{uuid4().hex[:8]}")

    resp = await client.post(
        "/api/v1/incidents/",
        headers=auth_header(token),
        json={
            "camera_id": camera_id,
            "threat_type": threat_type,
            "description": "test incident",
            "risk_level": risk_level,
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestAlertsRequireAuth:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path", [
        ("GET", "/api/v1/alerts/"),
        ("GET", "/api/v1/alerts/count"),
    ])
    async def test_endpoint_requires_auth(self, client, method, path):
        resp = await client.request(method, path)
        assert resp.status_code == 401


class TestIncidentRaisesRealAlert:
    """Confirms alerts are created from confirmed incidents, not fabricated."""

    @pytest.mark.asyncio
    async def test_high_risk_incident_creates_alert(self, client, operator_token):
        incident = await _create_incident(client, operator_token, risk_level="HIGH")

        resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        data = resp.json()
        assert data["meta"]["total_items"] == 1
        alert = data["data"][0]
        assert alert["incident_id"] == incident["id"]
        assert alert["severity"] == "HIGH"
        assert alert["camera_id"] == incident["camera_id"]

    @pytest.mark.asyncio
    async def test_low_risk_incident_creates_no_alert(self, client, operator_token):
        await _create_incident(client, operator_token, risk_level="LOW")

        resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        data = resp.json()
        assert data["meta"]["total_items"] == 0

    @pytest.mark.asyncio
    async def test_critical_incident_creates_critical_alert(self, client, operator_token):
        await _create_incident(client, operator_token, threat_type="rifle", risk_level="CRITICAL")

        resp = await client.get(
            "/api/v1/alerts/", headers=auth_header(operator_token), params={"severity": "CRITICAL"}
        )
        data = resp.json()
        assert data["meta"]["total_items"] == 1
        assert data["data"][0]["severity"] == "CRITICAL"


class TestAlertAcknowledge:
    @pytest.mark.asyncio
    async def test_acknowledge_real_alert(self, client, operator_token):
        await _create_incident(client, operator_token, risk_level="HIGH")
        list_resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        alert_id = list_resp.json()["data"][0]["id"]

        resp = await client.put(
            f"/api/v1/alerts/{alert_id}/acknowledge",
            headers=auth_header(operator_token),
            json={"notes": "Confirmed real threat, dispatching security"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ACKNOWLEDGED"
        assert data["is_acknowledged"] is True
        assert data["acknowledged_by"] == "op-001"
        assert data["acknowledgement_notes"] == "Confirmed real threat, dispatching security"

    @pytest.mark.asyncio
    async def test_viewer_cannot_acknowledge(self, client, operator_token, viewer_token):
        await _create_incident(client, operator_token, risk_level="HIGH")
        list_resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        alert_id = list_resp.json()["data"][0]["id"]

        resp = await client.put(
            f"/api/v1/alerts/{alert_id}/acknowledge",
            headers=auth_header(viewer_token),
            json={},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_double_acknowledge_returns_409(self, client, operator_token):
        await _create_incident(client, operator_token, risk_level="HIGH")
        list_resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        alert_id = list_resp.json()["data"][0]["id"]

        await client.put(f"/api/v1/alerts/{alert_id}/acknowledge", headers=auth_header(operator_token), json={})
        resp = await client.put(f"/api/v1/alerts/{alert_id}/acknowledge", headers=auth_header(operator_token), json={})
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_returns_404(self, client, operator_token):
        resp = await client.put(
            "/api/v1/alerts/00000000-0000-0000-0000-000000000000/acknowledge",
            headers=auth_header(operator_token),
            json={},
        )
        assert resp.status_code == 404


class TestAlertDismiss:
    @pytest.mark.asyncio
    async def test_dismiss_real_alert(self, client, operator_token):
        await _create_incident(client, operator_token, risk_level="HIGH")
        list_resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        alert_id = list_resp.json()["data"][0]["id"]

        resp = await client.put(
            f"/api/v1/alerts/{alert_id}/dismiss",
            headers=auth_header(operator_token),
            json={"reason": "Confirmed false alarm"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DISMISSED"
        assert data["dismissed_by"] == "op-001"


class TestAlertCounts:
    @pytest.mark.asyncio
    async def test_counts_reflect_real_alerts(self, client, operator_token):
        await _create_incident(client, operator_token, risk_level="HIGH")
        await _create_incident(client, operator_token, risk_level="CRITICAL")

        resp = await client.get("/api/v1/alerts/count", headers=auth_header(operator_token))
        data = resp.json()
        assert data["total_unacknowledged"] == 2
        assert data["by_severity"]["HIGH"] == 1
        assert data["by_severity"]["CRITICAL"] == 1

    @pytest.mark.asyncio
    async def test_acknowledged_alert_excluded_from_count(self, client, operator_token):
        await _create_incident(client, operator_token, risk_level="HIGH")
        list_resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        alert_id = list_resp.json()["data"][0]["id"]
        await client.put(f"/api/v1/alerts/{alert_id}/acknowledge", headers=auth_header(operator_token), json={})

        resp = await client.get("/api/v1/alerts/count", headers=auth_header(operator_token))
        assert resp.json()["total_unacknowledged"] == 0


class TestNotificationHistory:
    @pytest.mark.asyncio
    async def test_admin_sees_real_notification_log(self, client, operator_token, admin_token):
        await _create_incident(client, operator_token, risk_level="HIGH")
        list_resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        alert_id = list_resp.json()["data"][0]["id"]

        resp = await client.get(
            f"/api/v1/alerts/{alert_id}/notifications", headers=auth_header(admin_token)
        )
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        # Default channel is "console" and always succeeds
        assert logs[0]["channel"] == "console"
        assert logs[0]["status"] == "SENT"

    @pytest.mark.asyncio
    async def test_operator_cannot_view_notification_history(self, client, operator_token):
        await _create_incident(client, operator_token, risk_level="HIGH")
        list_resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        alert_id = list_resp.json()["data"][0]["id"]

        resp = await client.get(
            f"/api/v1/alerts/{alert_id}/notifications", headers=auth_header(operator_token)
        )
        assert resp.status_code == 403


class TestGetSingleAlert:
    @pytest.mark.asyncio
    async def test_get_real_alert_by_id(self, client, operator_token):
        incident = await _create_incident(client, operator_token, risk_level="HIGH")
        list_resp = await client.get("/api/v1/alerts/", headers=auth_header(operator_token))
        alert_id = list_resp.json()["data"][0]["id"]

        resp = await client.get(f"/api/v1/alerts/{alert_id}", headers=auth_header(operator_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["incident_id"] == incident["id"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_alert_returns_404(self, client, operator_token):
        resp = await client.get(
            "/api/v1/alerts/00000000-0000-0000-0000-000000000000", headers=auth_header(operator_token)
        )
        assert resp.status_code == 404
