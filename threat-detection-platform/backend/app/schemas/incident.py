"""
Incident Schemas
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class IncidentCreateRequest(BaseModel):
    """Manual incident creation (by operators)."""

    camera_id: str = Field(description="Source camera ID")
    threat_type: str = Field(description="Threat type (handgun, rifle, knife)")
    description: str = Field(default="", max_length=1000, description="Incident description")
    risk_level: str = Field(default="MEDIUM", description="Risk level override")


class IncidentStatusUpdate(BaseModel):
    """Update incident status."""

    status: str = Field(description="New status: ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE")
    notes: Optional[str] = Field(default=None, max_length=2000, description="Resolution notes")


class IncidentResponse(BaseModel):
    """Incident detail response."""

    id: str
    incident_number: int
    camera_id: str
    threat_type: str
    confidence: float
    risk_score: float
    risk_level: str
    status: str
    track_id: int | None = None
    location_id: str | None = None
    location_name: str = ""
    building: str = ""
    zone: str = ""
    latitude: float | None = None
    longitude: float | None = None
    weapon_count: int = 1
    frames_confirmed: int = 0
    description: str = ""
    acknowledged_by: str | None = None
    acknowledged_at: str | None = None
    resolved_by: str | None = None
    resolved_at: str | None = None
    resolution_notes: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    """Incident list item (summary)."""

    id: str
    incident_number: int
    camera_id: str
    threat_type: str
    risk_score: float
    risk_level: str
    status: str
    location_name: str = ""
    latitude: float | None = None
    longitude: float | None = None
    created_at: str

    model_config = {"from_attributes": True}
