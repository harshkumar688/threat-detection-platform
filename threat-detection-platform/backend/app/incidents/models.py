"""
Incident Domain Models

Defines the core data structures for incidents, their lifecycle states,
creation/update DTOs, and audit entries.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    """Incident lifecycle states."""

    OPEN = "OPEN"
    """Newly created incident, awaiting operator response."""

    ACKNOWLEDGED = "ACKNOWLEDGED"
    """Operator has seen the incident and is investigating."""

    RESOLVED = "RESOLVED"
    """Threat has been handled and incident is closed."""

    FALSE_POSITIVE = "FALSE_POSITIVE"
    """Detection was incorrect — no actual threat existed."""


# Valid state transitions
VALID_TRANSITIONS: Dict[IncidentStatus, List[IncidentStatus]] = {
    IncidentStatus.OPEN: [IncidentStatus.ACKNOWLEDGED, IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE],
    IncidentStatus.ACKNOWLEDGED: [IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE],
    IncidentStatus.RESOLVED: [],        # Terminal state
    IncidentStatus.FALSE_POSITIVE: [],  # Terminal state
}


def is_valid_transition(from_status: IncidentStatus, to_status: IncidentStatus) -> bool:
    """Check if a state transition is allowed."""
    return to_status in VALID_TRANSITIONS.get(from_status, [])


class Incident(BaseModel):
    """
    Core incident entity.

    Represents a confirmed security threat that requires human attention.
    """

    # Identity
    id: UUID = Field(default_factory=uuid4, description="Unique incident identifier")
    incident_number: int = Field(default=0, description="Sequential human-readable number")

    # Threat details
    camera_id: str = Field(description="Source camera identifier")
    threat_type: str = Field(description="Weapon class (handgun, rifle, knife)")
    confidence: float = Field(ge=0.0, le=1.0, description="Average detection confidence")
    risk_score: float = Field(ge=0.0, le=100.0, description="Computed risk score (0-100)")
    risk_level: str = Field(description="Risk classification (LOW/MEDIUM/HIGH/CRITICAL)")
    track_id: Optional[int] = Field(default=None, description="Associated tracker track ID")

    # Location (denormalized snapshot captured at creation time — see
    # app.cameras.models.LocationSnapshot; this record intentionally does
    # NOT live-reference the Location table so historical incidents remain
    # accurate even if the camera/location is later edited or reassigned)
    location_id: Optional[UUID] = Field(default=None, description="Linked Location ID at time of incident")
    location_name: str = Field(default="", description="Camera location name at time of incident")
    building: str = Field(default="", description="Building name at time of incident")
    zone: str = Field(default="", description="Zone/section at time of incident")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Location latitude, if applicable")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Location longitude, if applicable")
    location_metadata: Dict = Field(default_factory=dict, description="Additional location data")

    # Status
    status: IncidentStatus = Field(default=IncidentStatus.OPEN, description="Current lifecycle state")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = Field(default=None)
    resolved_at: Optional[datetime] = Field(default=None)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Operator info
    acknowledged_by: Optional[str] = Field(default=None, description="User who acknowledged")
    resolved_by: Optional[str] = Field(default=None, description="User who resolved")
    resolution_notes: Optional[str] = Field(default=None, description="Notes added at resolution")

    # Metadata
    weapon_count: int = Field(default=1, ge=0)
    frames_confirmed: int = Field(default=0, ge=0)
    description: str = Field(default="")

    model_config = {"from_attributes": True}


class IncidentCreate(BaseModel):
    """DTO for creating a new incident."""

    camera_id: str
    threat_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    risk_level: str
    track_id: Optional[int] = None
    location_id: Optional[UUID] = None
    location_name: str = ""
    building: str = ""
    zone: str = ""
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    location_metadata: Dict = Field(default_factory=dict)
    weapon_count: int = 1
    frames_confirmed: int = 0
    description: str = ""


class IncidentUpdate(BaseModel):
    """DTO for updating an incident (status transition)."""

    status: IncidentStatus
    user_id: Optional[str] = None
    notes: Optional[str] = None


class AuditEntry(BaseModel):
    """A single audit log entry for an incident."""

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    action: str = Field(description="Action performed (created, status_changed, etc.)")
    old_value: Optional[str] = Field(default=None)
    new_value: Optional[str] = Field(default=None)
    user_id: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}
