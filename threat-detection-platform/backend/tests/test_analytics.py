"""
Analytics Service Tests

Validates that all analytics metrics are computed from real data.
Uses in-memory repository with known test incidents.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.analytics.service import AnalyticsService
from app.incidents import IncidentCreate, IncidentService, IncidentStatus, IncidentUpdate, InMemoryIncidentRepository


@pytest.fixture
def repo():
    return InMemoryIncidentRepository()


@pytest.fixture
def incident_service(repo):
    return IncidentService(repo)


@pytest.fixture
def analytics(repo):
    return AnalyticsService(repo)


async def _seed_incidents(service: IncidentService, count: int = 5):
    """Seed test incidents with variety."""
    configs = [
        ("cam-01", "handgun", 0.85, 75.0, "HIGH", "Lobby"),
        ("cam-02", "rifle", 0.92, 90.0, "CRITICAL", "Entrance"),
        ("cam-01", "knife", 0.65, 40.0, "MEDIUM", "Lobby"),
        ("cam-03", "handgun", 0.78, 68.0, "HIGH", "Parking"),
        ("cam-02", "rifle", 0.88, 85.0, "CRITICAL", "Entrance"),
    ]
    incidents = []
    for i, (cam, weapon, conf, score, level, loc) in enumerate(configs[:count]):
        inc = await service.create_incident(IncidentCreate(
            camera_id=cam,
            threat_type=weapon,
            confidence=conf,
            risk_score=score,
            risk_level=level,
            location_name=loc,
            track_id=i + 100,
        ))
        incidents.append(inc)
    return incidents


class TestSummary:
    @pytest.mark.asyncio
    async def test_empty_summary(self, analytics):
        result = await analytics.get_summary()
        assert result["total_incidents"] == 0
        assert result["open_incidents"] == 0
        assert result["total_detections_today"] == 0

    @pytest.mark.asyncio
    async def test_summary_with_data(self, analytics, incident_service):
        await _seed_incidents(incident_service, 5)
        result = await analytics.get_summary()
        assert result["total_incidents"] == 5
        assert result["open_incidents"] == 5  # All OPEN by default

    @pytest.mark.asyncio
    async def test_severity_breakdown(self, analytics, incident_service):
        await _seed_incidents(incident_service, 5)
        result = await analytics.get_summary()
        assert "CRITICAL" in result["incidents_by_severity"]
        assert result["incidents_by_severity"]["CRITICAL"] == 2
        assert result["incidents_by_severity"]["HIGH"] == 2


class TestTimeline:
    @pytest.mark.asyncio
    async def test_empty_timeline(self, analytics):
        result = await analytics.get_incidents_timeline("daily", 7)
        assert result["total"] == 0
        assert len(result["data"]) == 7  # Still returns 7 day buckets with zeros

    @pytest.mark.asyncio
    async def test_timeline_with_data(self, analytics, incident_service):
        await _seed_incidents(incident_service, 3)
        result = await analytics.get_incidents_timeline("daily", 7)
        # Today's bucket should have 3
        assert result["total"] >= 3

    @pytest.mark.asyncio
    async def test_hourly_granularity(self, analytics, incident_service):
        await _seed_incidents(incident_service, 2)
        result = await analytics.get_incidents_timeline("hourly", 1)
        assert result["granularity"] == "hourly"
        assert len(result["data"]) == 24  # 24 hours in 1 day


class TestDistributions:
    @pytest.mark.asyncio
    async def test_weapon_distribution(self, analytics, incident_service):
        await _seed_incidents(incident_service, 5)
        result = await analytics.get_weapon_distribution()
        assert result["total"] == 5
        names = [d["name"] for d in result["data"]]
        assert "handgun" in names
        assert "rifle" in names

    @pytest.mark.asyncio
    async def test_risk_level_distribution(self, analytics, incident_service):
        await _seed_incidents(incident_service, 5)
        result = await analytics.get_risk_level_distribution()
        assert result["total"] == 5
        # CRITICAL=2, HIGH=2, MEDIUM=1
        critical = next(d for d in result["data"] if d["name"] == "CRITICAL")
        assert critical["count"] == 2

    @pytest.mark.asyncio
    async def test_camera_distribution(self, analytics, incident_service):
        await _seed_incidents(incident_service, 5)
        result = await analytics.get_camera_distribution()
        assert result["total"] == 5
        # cam-01 → Lobby (2), cam-02 → Entrance (2), cam-03 → Parking (1)
        lobby = next(d for d in result["data"] if d["name"] == "Lobby")
        assert lobby["count"] == 2

    @pytest.mark.asyncio
    async def test_percentages_sum_to_100(self, analytics, incident_service):
        await _seed_incidents(incident_service, 5)
        result = await analytics.get_weapon_distribution()
        total_pct = sum(d["percentage"] for d in result["data"])
        assert abs(total_pct - 100.0) < 1.0  # Within rounding

    @pytest.mark.asyncio
    async def test_empty_distribution(self, analytics):
        result = await analytics.get_weapon_distribution()
        assert result["total"] == 0
        assert result["data"] == []


class TestHourlyTrend:
    @pytest.mark.asyncio
    async def test_hourly_trend_24_buckets(self, analytics, incident_service):
        await _seed_incidents(incident_service, 3)
        result = await analytics.get_hourly_trend(days=7)
        assert len(result["data"]) == 24
        # Current hour should have incidents
        current_hour = datetime.now(timezone.utc).hour
        assert result["data"][current_hour]["count"] >= 3


class TestResolutionStatus:
    @pytest.mark.asyncio
    async def test_all_open(self, analytics, incident_service):
        await _seed_incidents(incident_service, 3)
        result = await analytics.get_resolution_status()
        assert result["total"] == 3
        open_item = next(d for d in result["data"] if d["name"] == "OPEN")
        assert open_item["count"] == 3

    @pytest.mark.asyncio
    async def test_mixed_statuses(self, analytics, incident_service, repo):
        incidents = await _seed_incidents(incident_service, 3)
        # Resolve one
        await incident_service.update_status(
            incidents[0].id, IncidentUpdate(status=IncidentStatus.RESOLVED, user_id="op1")
        )
        result = await analytics.get_resolution_status()
        statuses = {d["name"]: d["count"] for d in result["data"]}
        assert statuses["RESOLVED"] == 1
        assert statuses["OPEN"] == 2


class TestFalsePositiveRate:
    @pytest.mark.asyncio
    async def test_insufficient_data(self, analytics, incident_service):
        await _seed_incidents(incident_service, 2)
        result = await analytics.get_false_positive_rate()
        assert result["rate"] is None
        assert "Insufficient" in result["note"]

    @pytest.mark.asyncio
    async def test_with_sufficient_data(self, analytics, incident_service):
        incidents = await _seed_incidents(incident_service, 5)
        # Resolve 4, mark 1 as false positive
        for inc in incidents[:4]:
            await incident_service.update_status(
                inc.id, IncidentUpdate(status=IncidentStatus.RESOLVED, user_id="op1")
            )
        await incident_service.update_status(
            incidents[4].id, IncidentUpdate(status=IncidentStatus.FALSE_POSITIVE, user_id="op1")
        )

        result = await analytics.get_false_positive_rate()
        assert result["rate"] is not None
        assert result["total_labeled"] == 5
        assert result["false_positives"] == 1
        assert result["true_positives"] == 4
        # Rate = 1/5 * 100 = 20.0%
        assert result["rate"] == 20.0
