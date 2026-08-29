"""
Analytics Router

All data comes from real incident records via AnalyticsService.
No fabricated numbers. Empty results returned when no data exists.

Endpoints:
- GET /analytics/summary               → Dashboard KPIs
- GET /analytics/incidents/timeline     → Incidents over time
- GET /analytics/incidents/by-camera    → Camera-wise distribution
- GET /analytics/incidents/by-severity  → Risk level distribution
- GET /analytics/incidents/by-weapon    → Weapon category distribution
- GET /analytics/incidents/by-hour      → Hour-of-day trends
- GET /analytics/incidents/by-status    → Resolution status breakdown
- GET /analytics/false-positive-rate    → FP rate (from labeled data only)
"""

from fastapi import APIRouter, Depends, Query

from app.analytics.service import AnalyticsService
from app.api.deps import CurrentUser, get_current_user
from app.api.v1.incidents import _repo as incident_repo
from app.schemas.analytics import (
    AnalyticsSummary,
    DistributionResponse,
    TimelineResponse,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _get_analytics_service() -> AnalyticsService:
    """Get analytics service instance backed by the incident repository."""
    return AnalyticsService(incident_repo)


@router.get(
    "/summary",
    response_model=AnalyticsSummary,
    summary="Dashboard summary KPIs",
    description="Key metrics computed from real incident data. Returns zeros when no data exists.",
)
async def get_summary(user: CurrentUser = Depends(get_current_user)):
    service = _get_analytics_service()
    return await service.get_summary(camera_count=0)


@router.get(
    "/incidents/timeline",
    response_model=TimelineResponse,
    summary="Incidents over time",
    description="Time series of incident counts. Granularity: hourly, daily, weekly.",
)
async def get_incidents_timeline(
    granularity: str = Query(default="daily", description="hourly, daily, weekly"),
    days: int = Query(default=7, ge=1, le=90, description="Number of days to include"),
    user: CurrentUser = Depends(get_current_user),
):
    service = _get_analytics_service()
    return await service.get_incidents_timeline(granularity=granularity, days=days)


@router.get(
    "/detections/timeline",
    response_model=TimelineResponse,
    summary="Detection timeline (proxy)",
    description="Detection counts over time. Uses incident data as proxy until detection table is connected.",
)
async def get_detection_timeline(
    granularity: str = Query(default="daily", description="hourly, daily, weekly"),
    days: int = Query(default=7, ge=1, le=90),
    user: CurrentUser = Depends(get_current_user),
):
    service = _get_analytics_service()
    return await service.get_incidents_timeline(granularity=granularity, days=days)


@router.get(
    "/incidents/by-camera",
    response_model=DistributionResponse,
    summary="Incidents by camera/location",
    description="Distribution of incidents grouped by camera or location.",
)
async def get_incidents_by_camera(user: CurrentUser = Depends(get_current_user)):
    service = _get_analytics_service()
    return await service.get_camera_distribution()


@router.get(
    "/incidents/by-severity",
    response_model=DistributionResponse,
    summary="Incidents by risk level",
    description="Distribution of incidents by risk level (CRITICAL/HIGH/MEDIUM/LOW).",
)
async def get_incidents_by_severity(user: CurrentUser = Depends(get_current_user)):
    service = _get_analytics_service()
    return await service.get_risk_level_distribution()


@router.get(
    "/incidents/by-weapon",
    response_model=DistributionResponse,
    summary="Incidents by weapon type",
    description="Distribution of incidents by weapon category (handgun, rifle, knife).",
)
async def get_incidents_by_weapon(user: CurrentUser = Depends(get_current_user)):
    service = _get_analytics_service()
    return await service.get_weapon_distribution()


@router.get(
    "/incidents/by-hour",
    response_model=TimelineResponse,
    summary="Hour-wise incident trend",
    description="Incident counts aggregated by hour of day (0-23) to show peak activity times.",
)
async def get_incidents_by_hour(
    days: int = Query(default=7, ge=1, le=90),
    user: CurrentUser = Depends(get_current_user),
):
    service = _get_analytics_service()
    return await service.get_hourly_trend(days=days)


@router.get(
    "/incidents/by-status",
    response_model=DistributionResponse,
    summary="Resolution status breakdown",
    description="Distribution of incidents by current status (OPEN/ACKNOWLEDGED/RESOLVED/FALSE_POSITIVE).",
)
async def get_incidents_by_status(user: CurrentUser = Depends(get_current_user)):
    service = _get_analytics_service()
    return await service.get_resolution_status()


@router.get(
    "/false-positive-rate",
    summary="False positive rate",
    description=(
        "Computed from incidents that have been labeled as RESOLVED or FALSE_POSITIVE. "
        "Returns null if fewer than 5 labeled incidents exist. Never fabricated."
    ),
)
async def get_false_positive_rate(user: CurrentUser = Depends(get_current_user)):
    service = _get_analytics_service()
    return await service.get_false_positive_rate()
