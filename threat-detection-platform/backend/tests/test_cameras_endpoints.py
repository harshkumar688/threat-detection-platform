"""
Camera & Location API Endpoint Tests (HTTP level)

Verifies the full chain: HTTP request -> router -> CameraService/LocationService
-> InMemory repositories -> real response. Also verifies that incident
creation via the real /api/v1/incidents endpoint correctly resolves and
embeds a location snapshot from the camera's linked location.
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
    """Ensure clean camera/location/incident/alert stores before each test."""
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


async def _create_location(client, admin_token, name=None, **kwargs):
    body = {"name": name or f"Loc-{uuid4().hex[:8]}", **kwargs}
    resp = await client.post("/api/v1/locations/", headers=auth_header(admin_token), json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_camera(client, admin_token, name=None, location_id=None, **kwargs):
    body = {
        "name": name or f"cam-{uuid4().hex[:8]}",
        "stream_url": "rtsp://example.invalid/stream",
        **kwargs,
    }
    if location_id is not None:
        body["location_id"] = location_id
    resp = await client.post("/api/v1/cameras/", headers=auth_header(admin_token), json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# =============================================================================
# Locations
# =============================================================================

class TestLocationAuth:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path", [
        ("GET", "/api/v1/locations/"),
    ])
    async def test_requires_auth(self, client, method, path):
        resp = await client.request(method, path)
        assert resp.status_code == 401


class TestLocationCRUD:
    @pytest.mark.asyncio
    async def test_admin_creates_location(self, client, admin_token):
        location = await _create_location(
            client, admin_token, name="Main Entrance", building="HQ", zone="North",
            latitude=12.34, longitude=56.78,
        )
        assert location["name"] == "Main Entrance"
        assert location["building"] == "HQ"
        assert location["latitude"] == 12.34
        assert location["longitude"] == 56.78
        assert location["is_active"] is True

    @pytest.mark.asyncio
    async def test_operator_cannot_create_location(self, client, operator_token):
        resp = await client.post(
            "/api/v1/locations/",
            headers=auth_header(operator_token),
            json={"name": "Should Fail"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_duplicate_location_name_returns_409(self, client, admin_token):
        await _create_location(client, admin_token, name="Duplicate Lobby")
        resp = await client.post(
            "/api/v1/locations/",
            headers=auth_header(admin_token),
            json={"name": "Duplicate Lobby"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_locations(self, client, admin_token, viewer_token):
        await _create_location(client, admin_token, name="Loc A")
        await _create_location(client, admin_token, name="Loc B")

        resp = await client.get("/api/v1/locations/", headers=auth_header(viewer_token))
        assert resp.status_code == 200
        names = [l["name"] for l in resp.json()]
        assert "Loc A" in names and "Loc B" in names

    @pytest.mark.asyncio
    async def test_get_location_by_id(self, client, admin_token):
        location = await _create_location(client, admin_token, name="Get Me")
        resp = await client.get(f"/api/v1/locations/{location['id']}", headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    @pytest.mark.asyncio
    async def test_get_nonexistent_location_returns_404(self, client, admin_token):
        resp = await client.get(
            "/api/v1/locations/00000000-0000-0000-0000-000000000000",
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_location(self, client, admin_token):
        location = await _create_location(client, admin_token, name="Old Name")
        resp = await client.put(
            f"/api/v1/locations/{location['id']}",
            headers=auth_header(admin_token),
            json={"name": "New Name", "zone": "South"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"
        assert data["zone"] == "South"

    @pytest.mark.asyncio
    async def test_operator_cannot_update_location(self, client, admin_token, operator_token):
        location = await _create_location(client, admin_token, name="Locked")
        resp = await client.put(
            f"/api/v1/locations/{location['id']}",
            headers=auth_header(operator_token),
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_unused_location(self, client, admin_token):
        location = await _create_location(client, admin_token, name="Unused")
        resp = await client.delete(f"/api/v1/locations/{location['id']}", headers=auth_header(admin_token))
        assert resp.status_code == 204

        get_resp = await client.get(f"/api/v1/locations/{location['id']}", headers=auth_header(admin_token))
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_location_in_use_returns_409(self, client, admin_token):
        location = await _create_location(client, admin_token, name="In Use")
        await _create_camera(client, admin_token, name="cam-linked", location_id=location["id"])

        resp = await client.delete(f"/api/v1/locations/{location['id']}", headers=auth_header(admin_token))
        assert resp.status_code == 409


# =============================================================================
# Cameras
# =============================================================================

class TestCameraAuth:
    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/cameras/")
        assert resp.status_code == 401


class TestCameraCRUD:
    @pytest.mark.asyncio
    async def test_admin_creates_camera_without_location(self, client, admin_token):
        camera = await _create_camera(client, admin_token, name="cam-standalone")
        assert camera["name"] == "cam-standalone"
        assert camera["location_id"] is None
        assert camera["status"] == "offline"

    @pytest.mark.asyncio
    async def test_admin_creates_camera_with_location(self, client, admin_token):
        location = await _create_location(client, admin_token, name="Warehouse")
        camera = await _create_camera(client, admin_token, name="cam-wh", location_id=location["id"])
        assert camera["location_id"] == location["id"]

    @pytest.mark.asyncio
    async def test_create_camera_with_unknown_location_returns_404(self, client, admin_token):
        resp = await client.post(
            "/api/v1/cameras/",
            headers=auth_header(admin_token),
            json={
                "name": "cam-bad-loc",
                "stream_url": "rtsp://example.invalid",
                "location_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_operator_cannot_create_camera(self, client, operator_token):
        resp = await client.post(
            "/api/v1/cameras/",
            headers=auth_header(operator_token),
            json={"name": "cam-x", "stream_url": "rtsp://example.invalid"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_duplicate_camera_name_returns_409(self, client, admin_token):
        await _create_camera(client, admin_token, name="dup-cam")
        resp = await client.post(
            "/api/v1/cameras/",
            headers=auth_header(admin_token),
            json={"name": "dup-cam", "stream_url": "rtsp://example.invalid"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_cameras(self, client, admin_token, viewer_token):
        await _create_camera(client, admin_token, name="cam-list-1")
        await _create_camera(client, admin_token, name="cam-list-2")

        resp = await client.get("/api/v1/cameras/", headers=auth_header(viewer_token))
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "cam-list-1" in names and "cam-list-2" in names

    @pytest.mark.asyncio
    async def test_filter_cameras_by_location(self, client, admin_token):
        loc = await _create_location(client, admin_token, name="Filter Zone")
        await _create_camera(client, admin_token, name="cam-filtered", location_id=loc["id"])
        await _create_camera(client, admin_token, name="cam-unfiltered")

        resp = await client.get(
            "/api/v1/cameras/", headers=auth_header(admin_token), params={"location_id": loc["id"]}
        )
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert names == ["cam-filtered"]

    @pytest.mark.asyncio
    async def test_get_camera_by_id(self, client, admin_token):
        camera = await _create_camera(client, admin_token, name="cam-get")
        resp = await client.get(f"/api/v1/cameras/{camera['id']}", headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "cam-get"

    @pytest.mark.asyncio
    async def test_get_nonexistent_camera_returns_404(self, client, admin_token):
        resp = await client.get(
            "/api/v1/cameras/00000000-0000-0000-0000-000000000000",
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_camera_reassign_location(self, client, admin_token):
        camera = await _create_camera(client, admin_token, name="cam-move")
        loc = await _create_location(client, admin_token, name="New Home")

        resp = await client.put(
            f"/api/v1/cameras/{camera['id']}",
            headers=auth_header(admin_token),
            json={"location_id": loc["id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["location_id"] == loc["id"]

    @pytest.mark.asyncio
    async def test_operator_cannot_update_camera(self, client, admin_token, operator_token):
        camera = await _create_camera(client, admin_token, name="cam-locked")
        resp = await client.put(
            f"/api/v1/cameras/{camera['id']}",
            headers=auth_header(operator_token),
            json={"name": "cam-hacked"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_camera(self, client, admin_token):
        camera = await _create_camera(client, admin_token, name="cam-delete")
        resp = await client.delete(f"/api/v1/cameras/{camera['id']}", headers=auth_header(admin_token))
        assert resp.status_code == 204

        get_resp = await client.get(f"/api/v1/cameras/{camera['id']}", headers=auth_header(admin_token))
        assert get_resp.status_code == 404


class TestCameraLifecycle:
    @pytest.mark.asyncio
    async def test_operator_starts_and_stops_camera(self, client, admin_token, operator_token):
        camera = await _create_camera(client, admin_token, name="cam-lifecycle")

        start_resp = await client.post(
            f"/api/v1/cameras/{camera['id']}/start", headers=auth_header(operator_token)
        )
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "processing"

        stop_resp = await client.post(
            f"/api/v1/cameras/{camera['id']}/stop", headers=auth_header(operator_token)
        )
        assert stop_resp.status_code == 200
        assert stop_resp.json()["status"] == "offline"

    @pytest.mark.asyncio
    async def test_viewer_cannot_start_camera(self, client, admin_token, viewer_token):
        camera = await _create_camera(client, admin_token, name="cam-viewer-blocked")
        resp = await client.post(
            f"/api/v1/cameras/{camera['id']}/start", headers=auth_header(viewer_token)
        )
        assert resp.status_code == 403


# =============================================================================
# Incident <-> Camera/Location integration
# =============================================================================

class TestIncidentLocationIntegration:
    @pytest.mark.asyncio
    async def test_incident_creation_requires_real_camera(self, client, operator_token):
        resp = await client.post(
            "/api/v1/incidents/",
            headers=auth_header(operator_token),
            json={
                "camera_id": "00000000-0000-0000-0000-000000000000",
                "threat_type": "handgun",
                "risk_level": "HIGH",
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_incident_embeds_location_snapshot(self, client, admin_token, operator_token):
        location = await _create_location(
            client, admin_token, name="Snapshot Zone", building="B1", zone="Z1",
            latitude=1.111, longitude=2.222,
        )
        camera = await _create_camera(client, admin_token, name="cam-snapshot", location_id=location["id"])

        resp = await client.post(
            "/api/v1/incidents/",
            headers=auth_header(operator_token),
            json={"camera_id": camera["id"], "threat_type": "handgun", "risk_level": "HIGH"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["location_id"] == location["id"]
        assert data["location_name"] == "Snapshot Zone"
        assert data["building"] == "B1"
        assert data["zone"] == "Z1"
        assert data["latitude"] == 1.111
        assert data["longitude"] == 2.222

    @pytest.mark.asyncio
    async def test_incident_snapshot_immutable_after_location_rename(self, client, admin_token, operator_token):
        location = await _create_location(client, admin_token, name="Original Name")
        camera = await _create_camera(client, admin_token, name="cam-immutable", location_id=location["id"])

        create_resp = await client.post(
            "/api/v1/incidents/",
            headers=auth_header(operator_token),
            json={"camera_id": camera["id"], "threat_type": "handgun", "risk_level": "HIGH"},
        )
        incident = create_resp.json()
        assert incident["location_name"] == "Original Name"

        # Rename the location after incident creation
        await client.put(
            f"/api/v1/locations/{location['id']}",
            headers=auth_header(admin_token),
            json={"name": "Renamed Later"},
        )

        get_resp = await client.get(f"/api/v1/incidents/{incident['id']}", headers=auth_header(operator_token))
        assert get_resp.json()["location_name"] == "Original Name"

    @pytest.mark.asyncio
    async def test_incident_without_camera_location_has_empty_snapshot(self, client, admin_token, operator_token):
        camera = await _create_camera(client, admin_token, name="cam-no-location")

        resp = await client.post(
            "/api/v1/incidents/",
            headers=auth_header(operator_token),
            json={"camera_id": camera["id"], "threat_type": "handgun", "risk_level": "MEDIUM"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["location_id"] is None
        assert data["location_name"] == ""
        assert data["latitude"] is None
