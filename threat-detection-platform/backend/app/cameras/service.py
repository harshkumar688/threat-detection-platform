"""
Camera & Location Services

Business logic layer:
- LocationService: CRUD for physical locations, with delete-safety checks
  (a location still referenced by cameras cannot be deleted)
- CameraService: CRUD + status/lifecycle for camera devices, validates
  location_id references and resolves LocationSnapshot for incident
  creation

Routers call these services — never the repositories directly.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from .exceptions import (
    CameraNotFoundError,
    DuplicateCameraNameError,
    DuplicateLocationNameError,
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
)
from .repository import CameraRepository, LocationRepository

logger = logging.getLogger(__name__)


class LocationService:
    """
    Location management service.

    Usage:
        repo = InMemoryLocationRepository()
        service = LocationService(repo)

        location = await service.create_location(LocationCreate(name="Main Lobby", ...))
    """

    def __init__(self, repository: LocationRepository):
        self._repo = repository

    async def create_location(self, data: LocationCreate) -> Location:
        """
        Create a new location.

        Raises:
            DuplicateLocationNameError: If the name is already in use.
        """
        existing = await self._repo.get_by_name(data.name)
        if existing is not None:
            raise DuplicateLocationNameError(data.name)

        location = Location(
            name=data.name,
            building=data.building,
            floor=data.floor,
            zone=data.zone,
            description=data.description,
            latitude=data.latitude,
            longitude=data.longitude,
        )
        location = await self._repo.create(location)

        logger.info("Location created: %s (%s)", location.name, location.id)
        return location

    async def get_location(self, location_id: UUID) -> Location:
        """Retrieve a location by ID. Raises LocationNotFoundError if not found."""
        location = await self._repo.get_by_id(location_id)
        if location is None:
            raise LocationNotFoundError(location_id)
        return location

    async def update_location(self, location_id: UUID, data: LocationUpdate) -> Location:
        """
        Update a location's fields.

        Raises:
            LocationNotFoundError: If location not found.
            DuplicateLocationNameError: If renaming to a name already in use
                by a different location.
        """
        location = await self._repo.get_by_id(location_id)
        if location is None:
            raise LocationNotFoundError(location_id)

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != location.name:
            existing = await self._repo.get_by_name(update_data["name"])
            if existing is not None and existing.id != location_id:
                raise DuplicateLocationNameError(update_data["name"])

        for key, value in update_data.items():
            setattr(location, key, value)

        location = await self._repo.update(location)
        logger.info("Location updated: %s (%s)", location.name, location.id)
        return location

    async def delete_location(self, location_id: UUID, camera_repo: CameraRepository) -> None:
        """
        Delete a location.

        Raises:
            LocationNotFoundError: If location not found.
            LocationInUseError: If any camera still references this location.
                Cameras must be reassigned or removed first — deletion never
                cascades and silently detaches cameras.
        """
        location = await self._repo.get_by_id(location_id)
        if location is None:
            raise LocationNotFoundError(location_id)

        camera_count = await camera_repo.count_by_location(location_id)
        if camera_count > 0:
            raise LocationInUseError(location_id, camera_count)

        await self._repo.delete(location_id)
        logger.info("Location deleted: %s (%s)", location.name, location_id)

    async def list_locations(self, is_active: Optional[bool] = None) -> List[Location]:
        """List all locations, optionally filtered by active status."""
        return await self._repo.list_all(is_active=is_active)


class CameraService:
    """
    Camera management service.

    Usage:
        camera_repo = InMemoryCameraRepository()
        location_repo = InMemoryLocationRepository()
        service = CameraService(camera_repo, location_repo)

        camera = await service.create_camera(CameraCreate(name="Lobby Cam 1", ...))
    """

    def __init__(self, repository: CameraRepository, location_repository: LocationRepository):
        self._repo = repository
        self._location_repo = location_repository

    async def create_camera(self, data: CameraCreate) -> Camera:
        """
        Register a new camera.

        Validates:
        - Camera name is not already in use
        - If location_id is provided, that location must exist

        Raises:
            DuplicateCameraNameError: If the name is already in use.
            LocationNotFoundError: If location_id does not reference an existing location.
        """
        existing = await self._repo.get_by_name(data.name)
        if existing is not None:
            raise DuplicateCameraNameError(data.name)

        if data.location_id is not None:
            location = await self._location_repo.get_by_id(data.location_id)
            if location is None:
                raise LocationNotFoundError(data.location_id)

        camera = Camera(
            name=data.name,
            location_id=data.location_id,
            stream_url=data.stream_url,
            stream_type=data.stream_type,
            target_fps=data.target_fps,
            resolution_width=data.resolution_width,
            resolution_height=data.resolution_height,
            is_enabled=data.is_enabled,
            metadata=data.metadata,
            status=CameraStatus.OFFLINE,
        )
        camera = await self._repo.create(camera)

        logger.info("Camera registered: %s (%s)", camera.name, camera.id)
        return camera

    async def get_camera(self, camera_id: UUID) -> Camera:
        """Retrieve a camera by ID. Raises CameraNotFoundError if not found."""
        camera = await self._repo.get_by_id(camera_id)
        if camera is None:
            raise CameraNotFoundError(camera_id)
        return camera

    async def update_camera(self, camera_id: UUID, data: CameraUpdate) -> Camera:
        """
        Update a camera's configuration.

        Raises:
            CameraNotFoundError: If camera not found.
            DuplicateCameraNameError: If renaming to a name already in use.
            LocationNotFoundError: If location_id does not reference an existing location.
        """
        camera = await self._repo.get_by_id(camera_id)
        if camera is None:
            raise CameraNotFoundError(camera_id)

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != camera.name:
            existing = await self._repo.get_by_name(update_data["name"])
            if existing is not None and existing.id != camera_id:
                raise DuplicateCameraNameError(update_data["name"])

        if "location_id" in update_data and update_data["location_id"] is not None:
            location = await self._location_repo.get_by_id(update_data["location_id"])
            if location is None:
                raise LocationNotFoundError(update_data["location_id"])

        for key, value in update_data.items():
            setattr(camera, key, value)

        camera = await self._repo.update(camera)
        logger.info("Camera updated: %s (%s)", camera.name, camera.id)
        return camera

    async def delete_camera(self, camera_id: UUID) -> None:
        """
        Remove a camera from the system.

        Raises:
            CameraNotFoundError: If camera not found.
        """
        camera = await self._repo.get_by_id(camera_id)
        if camera is None:
            raise CameraNotFoundError(camera_id)

        await self._repo.delete(camera_id)
        logger.info("Camera deleted: %s (%s)", camera.name, camera_id)

    async def list_cameras(
        self,
        status: Optional[CameraStatus] = None,
        location_id: Optional[UUID] = None,
    ) -> List[Camera]:
        """List cameras with optional status/location filtering."""
        return await self._repo.list_all(status=status, location_id=location_id)

    async def start_stream(self, camera_id: UUID) -> Camera:
        """
        Mark a camera as actively processing.

        Raises:
            CameraNotFoundError: If camera not found.
        """
        camera = await self._repo.get_by_id(camera_id)
        if camera is None:
            raise CameraNotFoundError(camera_id)

        camera.status = CameraStatus.PROCESSING
        camera.last_online_at = datetime.now(timezone.utc)
        camera.error_message = None
        camera = await self._repo.update(camera)

        logger.info("Camera stream started: %s (%s)", camera.name, camera_id)
        return camera

    async def stop_stream(self, camera_id: UUID) -> Camera:
        """
        Mark a camera as offline (stream processing stopped).

        Raises:
            CameraNotFoundError: If camera not found.
        """
        camera = await self._repo.get_by_id(camera_id)
        if camera is None:
            raise CameraNotFoundError(camera_id)

        camera.status = CameraStatus.OFFLINE
        camera = await self._repo.update(camera)

        logger.info("Camera stream stopped: %s (%s)", camera.name, camera_id)
        return camera

    async def report_error(self, camera_id: UUID, error_message: str) -> Camera:
        """
        Mark a camera as errored with a diagnostic message.

        Raises:
            CameraNotFoundError: If camera not found.
        """
        camera = await self._repo.get_by_id(camera_id)
        if camera is None:
            raise CameraNotFoundError(camera_id)

        camera.status = CameraStatus.ERROR
        camera.error_message = error_message
        camera = await self._repo.update(camera)

        logger.warning("Camera error: %s (%s): %s", camera.name, camera_id, error_message)
        return camera

    async def resolve_location_snapshot(self, camera_id: UUID) -> LocationSnapshot:
        """
        Resolve the current LocationSnapshot for a camera, for embedding
        into a newly created incident.

        Returns an empty LocationSnapshot (all fields blank/None) if the
        camera has no linked location or the camera itself does not exist —
        callers creating incidents should never fail solely because location
        data is unavailable.
        """
        camera = await self._repo.get_by_id(camera_id)
        if camera is None or camera.location_id is None:
            return LocationSnapshot()

        location = await self._location_repo.get_by_id(camera.location_id)
        if location is None:
            return LocationSnapshot()

        return location.to_snapshot()
