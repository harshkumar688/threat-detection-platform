"""
Detection Schemas
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DetectionResponse(BaseModel):
    """Single detection event."""

    id: str
    camera_id: str
    timestamp: str
    class_label: str
    confidence: float
    bbox: Dict = Field(description="Bounding box {x1, y1, x2, y2}")
    track_id: int | None = None
    is_weapon: bool = False
    is_verified: bool = False
    frame_number: int = 0

    model_config = {"from_attributes": True}


class DetectionStatsResponse(BaseModel):
    """Detection statistics for a time period."""

    total_detections: int
    weapon_detections: int
    person_detections: int
    avg_confidence: float
    detections_per_hour: float
    time_range_start: str
    time_range_end: str
