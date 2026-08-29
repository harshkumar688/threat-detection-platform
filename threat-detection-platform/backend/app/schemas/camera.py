"""
Camera & Location Schemas
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Location Schemas
# =============================================================================

class LocationCreate(BaseModel):
    """Create a new location."""

    name: str = Field(min_length=1, max_length=100, description="Unique location name")
    building: str = Field(default="", max_length=100, description="Building name")
    floor: str = Field(default="", max_length=20, description="Floor/level")
    zone: str = Field(default="", max_length=50, description="Zone or section")
    description: str = Field(default="", max_length=1000, description="Free-text description")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="GPS latitude, if applicable")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="GPS longitude, if applicable")


class LocationUpdate(BaseModel):
    """Update location fields. Only provided fields are changed."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    building: Optional[str] = Field(default=None, max_length=100)
    floor: Optional[str] = Field(default=None, max_length=20)
    zone: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=1000)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    is_active: Optional[bool] = None


class LocationResponse(BaseModel):
    """Location details response."""

    id: str
    name: str
    building: str = ""
    floor: str = ""
    zone: str = ""
    description: str = ""
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool = True
    created_at: str

    model_config = {"from_attributes": True}


# =============================================================================
# Camera Schemas
# =============================================================================

class CameraCreate(BaseModel):
    """Create a new camera."""

    name: str = Field(min_length=1, max_length=100, description="Display name")
    location_id: Optional[str] = Field(default=None, description="Existing Location ID to link")
    stream_url: str = Field(min_length=1, max_length=500, description="RTSP/HTTP stream URL")
    stream_type: str = Field(default="rtsp", description="Stream type: rtsp, http, usb, file")
    target_fps: int = Field(default=15, ge=1, le=60, description="Target capture FPS")
    is_enabled: bool = Field(default=True, description="Whether camera auto-starts")
    metadata: Dict = Field(default_factory=dict, description="Flexible metadata")


class CameraUpdate(BaseModel):
    """Update camera configuration."""

    name: Optional[str] = Field(default=None, max_length=100)
    location_id: Optional[str] = Field(default=None, description="Reassign to a different location")
    stream_url: Optional[str] = Field(default=None, max_length=500)
    stream_type: Optional[str] = None
    target_fps: Optional[int] = Field(default=None, ge=1, le=60)
    is_enabled: Optional[bool] = None
    metadata: Optional[Dict] = None


class CameraResponse(BaseModel):
    """Camera details response."""

    id: str
    name: str
    location_id: str | None = None
    stream_url: str
    stream_type: str
    target_fps: int
    resolution_width: int | None = None
    resolution_height: int | None = None
    status: str
    is_enabled: bool
    last_online_at: str | None = None
    error_message: str | None = None
    metadata: Dict = {}
    created_at: str

    model_config = {"from_attributes": True}


class CameraStatusResponse(BaseModel):
    """Camera stream status."""

    id: str
    name: str
    status: str
    fps: float = 0.0
    frames_processed: int = 0
    last_detection_at: str | None = None
