"""
Detections Router

Endpoints:
- GET /detections/             → List recent detections (paginated)
- GET /detections/stats        → Detection statistics
- GET /detections/{id}         → Single detection detail
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_current_user, get_pagination
from app.core.exceptions import NotFoundError
from app.schemas.base import PaginatedResponse, PaginationMeta, PaginationParams
from app.schemas.detection import DetectionResponse, DetectionStatsResponse

router = APIRouter(prefix="/detections", tags=["Detections"])


@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="List recent detections",
    description="Paginated list of raw detection events with optional camera and class filtering.",
)
async def list_detections(
    camera_id: Optional[str] = Query(default=None, description="Filter by camera"),
    class_label: Optional[str] = Query(default=None, description="Filter by class (handgun, person, etc.)"),
    is_weapon: Optional[bool] = Query(default=None, description="Filter weapon detections only"),
    pagination: PaginationParams = Depends(get_pagination),
    user: CurrentUser = Depends(get_current_user),
):
    """
    List raw detection events.

    High-volume endpoint — always use pagination.
    In production, queries the detections table with time range limits.
    """
    return PaginatedResponse(
        data=[],
        meta=PaginationMeta(
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=0,
            total_pages=0,
        ),
    )


@router.get(
    "/stats",
    response_model=DetectionStatsResponse,
    summary="Detection statistics",
    description="Aggregate detection statistics for a time period.",
)
async def get_detection_stats(
    hours: int = Query(default=24, ge=1, le=168, description="Time range in hours"),
    camera_id: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    """Get aggregate detection statistics."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)

    return DetectionStatsResponse(
        total_detections=0,
        weapon_detections=0,
        person_detections=0,
        avg_confidence=0.0,
        detections_per_hour=0.0,
        time_range_start=start.isoformat(),
        time_range_end=now.isoformat(),
    )
