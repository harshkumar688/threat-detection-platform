"""
API Integration Tests

Tests all API endpoints for correct status codes, response formats,
authentication enforcement, and validation.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.security import create_access_token


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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


# =============================================================================
# Health & Root Tests
# =============================================================================

class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_root_returns_200(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        assert "docs" in response.json()


# =============================================================================
# Auth Tests
# =============================================================================

class TestAuthEndpoints:

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        response = await client.post("/api/v1/auth/login", json={
            "email": "admin@threatplatform.local",
            "password": "admin123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        response = await client.post("/api/v1/auth/login", json={
            "email": "admin@threatplatform.local",
            "password": "wrongpass",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        response = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "test123",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_register_new_user(self, client):
        response = await client.post("/api/v1/auth/register", json={
            "email": "newuser@test.com",
            "password": "securepass123",
            "full_name": "New User",
            "role": "viewer",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "viewer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client):
        # First registration
        await client.post("/api/v1/auth/register", json={
            "email": "dup@test.com",
            "password": "pass12345",
            "full_name": "Dup User",
            "role": "viewer",
        })
        # Duplicate
        response = await client.post("/api/v1/auth/register", json={
            "email": "dup@test.com",
            "password": "pass12345",
            "full_name": "Dup User",
            "role": "viewer",
        })
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, client):
        # Use a real login to obtain a token tied to an actual seeded user,
        # since /me now validates the token subject against real user records.
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "admin@threatplatform.local",
            "password": "admin123",
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        response = await client.get("/api/v1/auth/me", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert data["email"] == "admin@threatplatform.local"

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


# =============================================================================
# Camera Tests
# =============================================================================

class TestCameraEndpoints:

    @pytest.mark.asyncio
    async def test_list_cameras_requires_auth(self, client):
        response = await client.get("/api/v1/cameras/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_cameras_authenticated(self, client, viewer_token):
        response = await client.get("/api/v1/cameras/", headers=auth_header(viewer_token))
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_create_camera_admin(self, client, admin_token):
        response = await client.post("/api/v1/cameras/", headers=auth_header(admin_token), json={
            "name": "Test Camera",
            "stream_url": "rtsp://192.168.1.100/stream",
            "stream_type": "rtsp",
            "location_name": "Lobby",
            "target_fps": 15,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Camera"
        assert data["status"] == "offline"

    @pytest.mark.asyncio
    async def test_create_camera_viewer_forbidden(self, client, viewer_token):
        response = await client.post("/api/v1/cameras/", headers=auth_header(viewer_token), json={
            "name": "Bad",
            "stream_url": "rtsp://x",
        })
        assert response.status_code == 403


# =============================================================================
# Incident Tests
# =============================================================================

class TestIncidentEndpoints:

    @pytest.mark.asyncio
    async def test_list_incidents(self, client, viewer_token):
        response = await client.get("/api/v1/incidents/", headers=auth_header(viewer_token))
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data

    @pytest.mark.asyncio
    async def test_create_incident_operator(self, client, admin_token, operator_token):
        # Incidents require a real, registered camera — create one first.
        cam_resp = await client.post("/api/v1/cameras/", headers=auth_header(admin_token), json={
            "name": "Incident Test Camera",
            "stream_url": "rtsp://example.invalid/incident-test",
        })
        assert cam_resp.status_code == 201
        camera_id = cam_resp.json()["id"]

        response = await client.post("/api/v1/incidents/", headers=auth_header(operator_token), json={
            "camera_id": camera_id,
            "threat_type": "handgun",
            "description": "Manual report",
            "risk_level": "HIGH",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["threat_type"] == "handgun"
        assert data["status"] == "OPEN"

    @pytest.mark.asyncio
    async def test_create_incident_viewer_forbidden(self, client, viewer_token):
        response = await client.post("/api/v1/incidents/", headers=auth_header(viewer_token), json={
            "camera_id": "cam-01",
            "threat_type": "knife",
        })
        assert response.status_code == 403


# =============================================================================
# Alert Tests
# =============================================================================

class TestAlertEndpoints:

    @pytest.mark.asyncio
    async def test_list_alerts(self, client, viewer_token):
        response = await client.get("/api/v1/alerts/", headers=auth_header(viewer_token))
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_alert_counts(self, client, viewer_token):
        response = await client.get("/api/v1/alerts/count", headers=auth_header(viewer_token))
        assert response.status_code == 200
        data = response.json()
        assert "total_unread" in data
        assert "total_unacknowledged" in data


# =============================================================================
# Analytics Tests
# =============================================================================

class TestAnalyticsEndpoints:

    @pytest.mark.asyncio
    async def test_summary(self, client, viewer_token):
        response = await client.get("/api/v1/analytics/summary", headers=auth_header(viewer_token))
        assert response.status_code == 200
        data = response.json()
        assert "total_incidents" in data
        assert "active_cameras" in data

    @pytest.mark.asyncio
    async def test_timeline(self, client, viewer_token):
        response = await client.get("/api/v1/analytics/detections/timeline", headers=auth_header(viewer_token))
        assert response.status_code == 200
        assert "data" in response.json()

    @pytest.mark.asyncio
    async def test_by_severity(self, client, viewer_token):
        response = await client.get("/api/v1/analytics/incidents/by-severity", headers=auth_header(viewer_token))
        assert response.status_code == 200


# =============================================================================
# Error Format Tests
# =============================================================================

class TestErrorFormats:

    @pytest.mark.asyncio
    async def test_404_returns_standard_format(self, client, admin_token):
        response = await client.get("/api/v1/cameras/nonexistent-id", headers=auth_header(admin_token))
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    @pytest.mark.asyncio
    async def test_validation_error_format(self, client, admin_token):
        # Missing required field
        response = await client.post("/api/v1/cameras/", headers=auth_header(admin_token), json={
            "name": "",  # Too short (min_length=1)
        })
        assert response.status_code == 422
        data = response.json()
        assert data["status"] == "error"
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_401_returns_standard_format(self, client):
        response = await client.get("/api/v1/cameras/")
        assert response.status_code == 401
        data = response.json()
        assert data["status"] == "error"
        assert data["error"]["code"] == "UNAUTHORIZED"
