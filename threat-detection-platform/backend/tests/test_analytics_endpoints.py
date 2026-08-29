"""
Analytics API Endpoint Tests (HTTP level)

Verifies the full chain: HTTP request → router → AnalyticsService →
IncidentRepository → real aggregated response.

Confirms every analytics endpoint:
- Requires authentication
- Returns correct schema
- Reflects real incident data (seeded through the actual create_incident API,
  which now requires a real, registered camera)
- Contains no fabricated/hardcoded numbers
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.security import create_access_token
from app.api.v1.incidents import _repo as incident_repo
from app.api.v1.cameras import _camera_repo
from app.api.v1.locations import _location_repo


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def clear_incidents():
    """Ensure a clean incident + camera + location store before each test."""
    incident_repo.clear()
    _camera_repo.clear()
    _location_repo.clear()
    yield
    incident_repo.clear()
    _camera_repo.clear()
    _location_repo.clear()


@pytest.fixture
def operator_token():
    return create_access_token(subject="op-001", role="operator", extra_claims={"email": "op@test.com"})


@pytest.fixture
def admin_token():
    return create_access_token(subject="admin-001", role="admin", extra_claims={"email": "admin@test.com"})


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_camera(client, admin_token, name: str) -> str:
    """Register a real camera by name, returning its assigned UUID. Idempotent per name within a test."""
    resp = await client.post(
        "/api/v1/cameras/",
        headers=auth_header(admin_token),
        json={"name": name, "stream_url": f"rtsp://example.invalid/{name}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _get_or_register_camera(client, admin_token, camera_ref: str, registry: dict) -> str:
    """Resolve a friendly test label to a registered camera UUID, registering it on first use."""
    if camera_ref not in registry:
        registry[camera_ref] = await _register_camera(client, admin_token, camera_ref)
    return registry[camera_ref]


async def _create_incident(client, token, camera_ref, threat_type, risk_level="HIGH", admin_token=None, registry=None):
    """
    Create a real incident via the API.

    `camera_ref` is a friendly test label (e.g. "cam-01", "cam-lobby"). When
    a `registry` dict is passed, the same label resolves to the same
    registered camera UUID for the lifetime of that dict (i.e. one test),
    so tests that create multiple incidents "on the same camera" continue
    to work exactly as before — just backed by a real camera record instead
    of an arbitrary string. Without a registry, a fresh camera is always
    registered.
    """
    admin = admin_token or create_access_token(
        subject="admin-001", role="admin", extra_claims={"email": "admin@test.com"}
    )

    if registry is not None:
        camera_id = await _get_or_register_camera(client, admin, camera_ref, registry)
    else:
        camera_id = await _register_camera(client, admin, camera_ref)

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


class TestAnalyticsRequiresAuth:
    """Every analytics endpoint must reject unauthenticated requests."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", [
        "/api/v1/analytics/summary",
        "/api/v1/analytics/incidents/timeline",
        "/api/v1/analytics/detections/timeline",
        "/api/v1/analytics/incidents/by-camera",
        "/api/v1/analytics/incidents/by-severity",
        "/api/v1/analytics/incidents/by-weapon",
        "/api/v1/analytics/incidents/by-hour",
        "/api/v1/analytics/incidents/by-status",
        "/api/v1/analytics/false-positive-rate",
    ])
    async def test_endpoint_requires_auth(self, client, path):
        resp = await client.get(path)
        assert resp.status_code == 401


class TestSummaryEndpoint:
    @pytest.mark.asyncio
    async def test_empty_summary_returns_zeros(self, client, operator_token):
        resp = await client.get("/api/v1/analytics/summary", headers=auth_header(operator_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_incidents"] == 0
        assert data["open_incidents"] == 0
        assert data["incidents_by_severity"] == {}

    @pytest.mark.asyncio
    async def test_summary_reflects_created_incidents(self, client, operator_token):
        await _create_incident(client, operator_token, "cam-01", "handgun", "HIGH")
        await _create_incident(client, operator_token, "cam-02", "rifle", "CRITICAL")

        resp = await client.get("/api/v1/analytics/summary", headers=auth_header(operator_token))
        data = resp.json()
        assert data["total_incidents"] == 2
        assert data["open_incidents"] == 2
        assert data["incidents_by_severity"]["HIGH"] == 1
        assert data["incidents_by_severity"]["CRITICAL"] == 1


class TestWeaponDistributionEndpoint:
    @pytest.mark.asyncio
    async def test_reflects_real_weapon_types(self, client, operator_token):
        registry = {}
        await _create_incident(client, operator_token, "cam-01", "handgun", registry=registry)
        await _create_incident(client, operator_token, "cam-01", "handgun", registry=registry)
        await _create_incident(client, operator_token, "cam-02", "knife", registry=registry)

        resp = await client.get("/api/v1/analytics/incidents/by-weapon", headers=auth_header(operator_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        by_name = {d["name"]: d["count"] for d in data["data"]}
        assert by_name["handgun"] == 2
        assert by_name["knife"] == 1

    @pytest.mark.asyncio
    async def test_empty_returns_no_fabricated_data(self, client, operator_token):
        resp = await client.get("/api/v1/analytics/incidents/by-weapon", headers=auth_header(operator_token))
        data = resp.json()
        assert data["total"] == 0
        assert data["data"] == []


class TestRiskLevelDistributionEndpoint:
    @pytest.mark.asyncio
    async def test_reflects_real_risk_levels(self, client, operator_token):
        registry = {}
        await _create_incident(client, operator_token, "cam-01", "handgun", "CRITICAL", registry=registry)
        await _create_incident(client, operator_token, "cam-01", "knife", "LOW", registry=registry)

        resp = await client.get("/api/v1/analytics/incidents/by-severity", headers=auth_header(operator_token))
        data = resp.json()
        by_name = {d["name"]: d["count"] for d in data["data"]}
        assert by_name["CRITICAL"] == 1
        assert by_name["LOW"] == 1


class TestCameraDistributionEndpoint:
    @pytest.mark.asyncio
    async def test_reflects_real_cameras(self, client, operator_token):
        registry = {}
        await _create_incident(client, operator_token, "cam-lobby", "handgun", registry=registry)
        await _create_incident(client, operator_token, "cam-lobby", "knife", registry=registry)
        await _create_incident(client, operator_token, "cam-parking", "rifle", registry=registry)

        resp = await client.get("/api/v1/analytics/incidents/by-camera", headers=auth_header(operator_token))
        data = resp.json()
        # Grouped by the real camera_id (a UUID) since these test incidents
        # have no linked Location — location_name falls back to camera_id.
        counts = sorted(d["count"] for d in data["data"])
        assert counts == [1, 2]


class TestResolutionStatusEndpoint:
    @pytest.mark.asyncio
    async def test_reflects_real_statuses(self, client, operator_token):
        inc1 = await _create_incident(client, operator_token, "cam-01", "handgun")
        await _create_incident(client, operator_token, "cam-02", "knife")

        # Resolve one via the real status update endpoint
        resp = await client.put(
            f"/api/v1/incidents/{inc1['id']}/status",
            headers=auth_header(operator_token),
            json={"status": "RESOLVED", "notes": "handled"},
        )
        assert resp.status_code == 200

        resp = await client.get("/api/v1/analytics/incidents/by-status", headers=auth_header(operator_token))
        data = resp.json()
        by_name = {d["name"]: d["count"] for d in data["data"]}
        assert by_name["RESOLVED"] == 1
        assert by_name["OPEN"] == 1


class TestTimelineEndpoint:
    @pytest.mark.asyncio
    async def test_timeline_reflects_todays_incident(self, client, operator_token):
        await _create_incident(client, operator_token, "cam-01", "handgun")

        resp = await client.get(
            "/api/v1/analytics/incidents/timeline",
            headers=auth_header(operator_token),
            params={"granularity": "daily", "days": 7},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["data"]) == 7

    @pytest.mark.asyncio
    async def test_empty_timeline_has_zero_buckets_not_fabricated(self, client, operator_token):
        resp = await client.get(
            "/api/v1/analytics/incidents/timeline",
            headers=auth_header(operator_token),
            params={"granularity": "daily", "days": 7},
        )
        data = resp.json()
        assert data["total"] == 0
        assert all(point["count"] == 0 for point in data["data"])


class TestHourlyTrendEndpoint:
    @pytest.mark.asyncio
    async def test_hourly_trend_has_24_hours(self, client, operator_token):
        await _create_incident(client, operator_token, "cam-01", "handgun")

        resp = await client.get(
            "/api/v1/analytics/incidents/by-hour", headers=auth_header(operator_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 24
        assert data["total"] >= 1


class TestFalsePositiveRateEndpoint:
    @pytest.mark.asyncio
    async def test_returns_null_when_insufficient_data(self, client, operator_token):
        await _create_incident(client, operator_token, "cam-01", "handgun")

        resp = await client.get(
            "/api/v1/analytics/false-positive-rate", headers=auth_header(operator_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate"] is None
        assert "Insufficient" in data["note"]

    @pytest.mark.asyncio
    async def test_computes_real_rate_from_labeled_incidents(self, client, operator_token):
        incidents = []
        for i in range(5):
            inc = await _create_incident(client, operator_token, f"cam-{i}", "handgun")
            incidents.append(inc)

        # Resolve 4 as true positives, 1 as false positive
        for inc in incidents[:4]:
            await client.put(
                f"/api/v1/incidents/{inc['id']}/status",
                headers=auth_header(operator_token),
                json={"status": "RESOLVED"},
            )
        await client.put(
            f"/api/v1/incidents/{incidents[4]['id']}/status",
            headers=auth_header(operator_token),
            json={"status": "FALSE_POSITIVE"},
        )

        resp = await client.get(
            "/api/v1/analytics/false-positive-rate", headers=auth_header(operator_token)
        )
        data = resp.json()
        assert data["rate"] == 20.0  # 1/5 = 20%
        assert data["total_labeled"] == 5
        assert data["false_positives"] == 1
        assert data["true_positives"] == 4
