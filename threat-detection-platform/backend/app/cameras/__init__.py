"""
Camera & Location Management Module

Manages physical camera devices and the locations where they are installed:
- Location: a physical place (building/floor/zone) with optional GPS coordinates
- Camera: a device with stream configuration, linked to a Location

Architecture:
    ┌────────────────────┐      ┌────────────────────┐
    │  Locations Router   │      │  Cameras Router     │
    └─────────┬───────────┘      └─────────┬───────────┘
              │                            │
    ┌─────────▼───────────┐      ┌─────────▼───────────┐
    │  LocationService     │◄─────│  CameraService       │
    └─────────┬───────────┘      └─────────┬───────────┘
              │                            │
    ┌─────────▼───────────┐      ┌─────────▼───────────┐
    │  LocationRepository  │      │  CameraRepository     │
    └──────────────────────┘      └──────────────────────┘

CameraService depends on LocationRepository (read-only) to validate that a
camera's assigned location_id exists and to resolve location snapshots
(name, coordinates) for consumers such as incident creation.

Incident records reference both the source camera_id and a denormalized
snapshot of that camera's configured location (location_id, location_name,
latitude, longitude) captured at incident-creation time — the same pattern
already used for other incident fields (risk_score, confidence, etc.) that
must not silently change if the camera/location is edited later.

This module does NOT implement any automatic dispatch, notification to
external authorities, or emergency-service integration of any kind.
"""

from .exceptions import (
    CameraError,
    CameraNotFoundError,
    DuplicateCameraNameError,
    DuplicateLocationNameError,
    LocationError,
    LocationInUseError,
    LocationNotFoundError,
)
from .models import (
    Camera,
    CameraCreate,
    CameraStatus,
    CameraUpdate,
    Location,
    LocationCreate,
    LocationSnapshot,
    LocationUpdate,
    StreamType,
)
from .repository import (
    CameraRepository,
    InMemoryCameraRepository,
    InMemoryLocationRepository,
    LocationRepository,
    SqlCameraRepository,
    SqlLocationRepository,
)
from .service import CameraService, LocationService

__all__ = [
    "CameraError",
    "CameraNotFoundError",
    "DuplicateCameraNameError",
    "DuplicateLocationNameError",
    "LocationError",
    "LocationInUseError",
    "LocationNotFoundError",
    "Camera",
    "CameraCreate",
    "CameraStatus",
    "CameraUpdate",
    "Location",
    "LocationCreate",
    "LocationSnapshot",
    "LocationUpdate",
    "StreamType",
    "CameraRepository",
    "InMemoryCameraRepository",
    "InMemoryLocationRepository",
    "LocationRepository",
    "SqlCameraRepository",
    "SqlLocationRepository",
    "CameraService",
    "LocationService",
]
