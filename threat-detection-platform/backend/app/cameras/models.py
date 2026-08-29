"""
Camera & Location Domain Models

Defines the core entities:
- Location: physical place where one or more cameras are installed
- Camera: a device with stream configuration, optionally linked to a Location
- LocationSnapshot: an immutable copy of a location's identifying details,
  captured onto an Incident at creation time so historical records don't
  silently change if the location is edited or deleted later.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StreamType(str, Enum):
    """Supported camera stream input types."""

    RTSP = "rtsp"
    HTTP = "http"
    USB = "usb"
    FILE = "file"


class CameraStatus(str, Enum):
    """Camera operational status."""

    OFFLINE = "offline"
    """Registered but not currently streaming."""

    ONLINE = "online"
    """Connected and receiving frames, detection not necessarily running."""

    PROCESSING = "processing"
    """Actively running the detection pipeline on this stream."""

    ERROR = "error"
    """Connection or processing failure; see error_message."""


# =============================================================================
# Location
# =============================================================================

class Location(BaseModel):
    """
    A physical location where cameras are installed.

    Latitude/longitude are optional — indoor cameras (e.g., "Server Room,
    Floor 2") may have no meaningful GPS coordinate, while outdoor/perimeter
    cameras typically do.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(description="Unique location name, e.g. 'Main Entrance Lobby'")
    building: str = Field(default="", description="Building name")
    floor: str = Field(default="", description="Floor/level identifier")
    zone: str = Field(default="", description="Zone or section within the building")
    description: str = Field(default="", description="Free-text description")

    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="GPS latitude, if applicable")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="GPS longitude, if applicable")

    is_active: bool = Field(default=True, description="Whether this location is currently in use")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    def to_snapshot(self) -> "LocationSnapshot":
        """Build an immutable snapshot for embedding into an incident record."""
        return LocationSnapshot(
            location_id=self.id,
            location_name=self.name,
            building=self.building,
            zone=self.zone,
            latitude=self.latitude,
            longitude=self.longitude,
        )


class LocationCreate(BaseModel):
    """DTO for creating a new location."""

    name: str = Field(min_length=1, max_length=100)
    building: str = Field(default="", max_length=100)
    floor: str = Field(default="", max_length=20)
    zone: str = Field(default="", max_length=50)
    description: str = Field(default="", max_length=1000)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)


class LocationUpdate(BaseModel):
    """DTO for updating a location. Only provided fields are changed."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    building: Optional[str] = Field(default=None, max_length=100)
    floor: Optional[str] = Field(default=None, max_length=20)
    zone: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=1000)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    is_active: Optional[bool] = None


class LocationSnapshot(BaseModel):
    """
    Immutable copy of a location's key details, embedded into an Incident
    at the moment it is created. Protects historical incident records from
    changing if the location is later renamed, moved, or deleted.
    """

    location_id: Optional[UUID] = None
    location_name: str = ""
    building: str = ""
    zone: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = {"from_attributes": True}


# =============================================================================
# Camera
# =============================================================================

class Camera(BaseModel):
    """
    A camera device with stream configuration.

    camera_id (the `id` field) is the stable identifier referenced by
    incident records, detections, and evidence. location_id points at the
    currently configured Location; incidents capture a LocationSnapshot
    instead of relying on this live reference, so they remain accurate even
    if the camera is later reassigned to a different location.
    """

    id: UUID = Field(default_factory=uuid4, description="Stable camera identifier (camera_id)")
    name: str = Field(description="Human-readable camera name")

    location_id: Optional[UUID] = Field(default=None, description="Linked Location, if any")

    # Stream configuration
    stream_url: str = Field(description="RTSP/HTTP/device URI")
    stream_type: StreamType = Field(default=StreamType.RTSP)
    target_fps: int = Field(default=15, ge=1, le=60)
    resolution_width: Optional[int] = Field(default=None, gt=0)
    resolution_height: Optional[int] = Field(default=None, gt=0)

    status: CameraStatus = Field(default=CameraStatus.OFFLINE)
    is_enabled: bool = Field(default=True, description="Whether this camera should auto-start")

    last_online_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)

    metadata: Dict = Field(default_factory=dict, description="Flexible vendor/device metadata")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class CameraCreate(BaseModel):
    """DTO for registering a new camera."""

    name: str = Field(min_length=1, max_length=100)
    location_id: Optional[UUID] = Field(default=None, description="Existing Location ID to link")
    stream_url: str = Field(min_length=1, max_length=500)
    stream_type: StreamType = Field(default=StreamType.RTSP)
    target_fps: int = Field(default=15, ge=1, le=60)
    resolution_width: Optional[int] = Field(default=None, gt=0)
    resolution_height: Optional[int] = Field(default=None, gt=0)
    is_enabled: bool = Field(default=True)
    metadata: Dict = Field(default_factory=dict)


class CameraUpdate(BaseModel):
    """DTO for updating camera configuration. Only provided fields are changed."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    location_id: Optional[UUID] = Field(default=None)
    stream_url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    stream_type: Optional[StreamType] = None
    target_fps: Optional[int] = Field(default=None, ge=1, le=60)
    resolution_width: Optional[int] = Field(default=None, gt=0)
    resolution_height: Optional[int] = Field(default=None, gt=0)
    is_enabled: Optional[bool] = None
    metadata: Optional[Dict] = None
