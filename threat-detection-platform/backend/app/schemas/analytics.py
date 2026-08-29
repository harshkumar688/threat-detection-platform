"""
Analytics Schemas
"""

from typing import Dict, List

from pydantic import BaseModel, Field


class AnalyticsSummary(BaseModel):
    """Dashboard summary KPIs."""

    total_incidents: int
    open_incidents: int
    total_detections_today: int
    active_cameras: int
    avg_response_time_seconds: float | None = None
    incidents_by_severity: Dict[str, int] = {}


class TimelinePoint(BaseModel):
    """Single data point in a time series."""

    timestamp: str
    count: int
    label: str = ""


class TimelineResponse(BaseModel):
    """Time series data for charts."""

    data: List[TimelinePoint]
    granularity: str = Field(description="hourly, daily, weekly, monthly")
    total: int = 0


class DistributionItem(BaseModel):
    """Item in a distribution chart."""

    name: str
    count: int
    percentage: float = 0.0


class DistributionResponse(BaseModel):
    """Distribution data (pie/bar charts)."""

    data: List[DistributionItem]
    total: int = 0
    group_by: str = ""
