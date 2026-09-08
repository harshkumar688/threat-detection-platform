"""
Camera & Location Repositories (Data Access Layer)

Abstract interfaces plus in-memory implementations for testing and
development without a database. A SQLAlchemy implementation can be added
later for production without changing any service or router code.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from .models import Camera, CameraStatus, Location


# =============================================================================
# Location Repository
# =============================================================================

class LocationRepository(ABC):
    """Abstract repository interface for locations."""

    @abstractmethod
    async def create(self, location: Location) -> Location:
        ...

    @abstractmethod
    async def get_by_id(self, location_id: UUID) -> Optional[Location]:
        ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Location]:
        ...

    @abstractmethod
    async def update(self, location: Location) -> Location:
        ...

    @abstractmethod
    async def delete(self, location_id: UUID) -> None:
        ...

    @abstractmethod
    async def list_all(self, is_active: Optional[bool] = None) -> List[Location]:
        ...


class InMemoryLocationRepository(LocationRepository):
    """In-memory implementation for testing and development. Not for production."""

    def __init__(self):
        self._locations: Dict[UUID, Location] = {}

    async def create(self, location: Location) -> Location:
        self._locations[location.id] = location
        return location

    async def get_by_id(self, location_id: UUID) -> Optional[Location]:
        return self._locations.get(location_id)

    async def get_by_name(self, name: str) -> Optional[Location]:
        for loc in self._locations.values():
            if loc.name.lower() == name.lower():
                return loc
        return None

    async def update(self, location: Location) -> Location:
        location.updated_at = datetime.now(timezone.utc)
        self._locations[location.id] = location
        return location

    async def delete(self, location_id: UUID) -> None:
        self._locations.pop(location_id, None)

    async def list_all(self, is_active: Optional[bool] = None) -> List[Location]:
        results = list(self._locations.values())
        if is_active is not None:
            results = [l for l in results if l.is_active == is_active]
        return sorted(results, key=lambda l: l.name)

    def clear(self):
        self._locations.clear()


# =============================================================================
# Camera Repository
# =============================================================================

class CameraRepository(ABC):
    """Abstract repository interface for cameras."""

    @abstractmethod
    async def create(self, camera: Camera) -> Camera:
        ...

    @abstractmethod
    async def get_by_id(self, camera_id: UUID) -> Optional[Camera]:
        ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Camera]:
        ...

    @abstractmethod
    async def update(self, camera: Camera) -> Camera:
        ...

    @abstractmethod
    async def delete(self, camera_id: UUID) -> None:
        ...

    @abstractmethod
    async def list_all(
        self,
        status: Optional[CameraStatus] = None,
        location_id: Optional[UUID] = None,
    ) -> List[Camera]:
        ...

    @abstractmethod
    async def count_by_location(self, location_id: UUID) -> int:
        """Count cameras currently linked to a location (for delete-safety checks)."""
        ...


class InMemoryCameraRepository(CameraRepository):
    """In-memory implementation for testing and development. Not for production."""

    def __init__(self):
        self._cameras: Dict[UUID, Camera] = {}

    async def create(self, camera: Camera) -> Camera:
        self._cameras[camera.id] = camera
        return camera

    async def get_by_id(self, camera_id: UUID) -> Optional[Camera]:
        return self._cameras.get(camera_id)

    async def get_by_name(self, name: str) -> Optional[Camera]:
        for cam in self._cameras.values():
            if cam.name.lower() == name.lower():
                return cam
        return None

    async def update(self, camera: Camera) -> Camera:
        camera.updated_at = datetime.now(timezone.utc)
        self._cameras[camera.id] = camera
        return camera

    async def delete(self, camera_id: UUID) -> None:
        self._cameras.pop(camera_id, None)

    async def list_all(
        self,
        status: Optional[CameraStatus] = None,
        location_id: Optional[UUID] = None,
    ) -> List[Camera]:
        results = list(self._cameras.values())
        if status is not None:
            results = [c for c in results if c.status == status]
        if location_id is not None:
            results = [c for c in results if c.location_id == location_id]
        return sorted(results, key=lambda c: c.name)

    async def count_by_location(self, location_id: UUID) -> int:
        return sum(1 for c in self._cameras.values() if c.location_id == location_id)

    def clear(self):
        self._cameras.clear()


# =============================================================================
# SQL-backed implementations (DocumentStore)
# =============================================================================

class SqlLocationRepository(LocationRepository):
    """Durable location repository backed by the generic document store."""

    def __init__(self):
        from app.db import DocumentStore
        self._store = DocumentStore("location")

    async def create(self, location: Location) -> Location:
        await self._store.upsert(str(location.id), location.model_dump(mode="json"))
        return location

    async def get_by_id(self, location_id: UUID) -> Optional[Location]:
        data = await self._store.get(str(location_id))
        return Location(**{k: v for k, v in data.items() if k != "_seq"}) if data else None

    async def get_by_name(self, name: str) -> Optional[Location]:
        for data in await self._store.list_all():
            loc = Location(**{k: v for k, v in data.items() if k != "_seq"})
            if loc.name.lower() == name.lower():
                return loc
        return None

    async def update(self, location: Location) -> Location:
        location.updated_at = datetime.now(timezone.utc)
        await self._store.upsert(str(location.id), location.model_dump(mode="json"))
        return location

    async def delete(self, location_id: UUID) -> None:
        await self._store.delete(str(location_id))

    async def list_all(self, is_active: Optional[bool] = None) -> List[Location]:
        results = [
            Location(**{k: v for k, v in d.items() if k != "_seq"})
            for d in await self._store.list_all()
        ]
        if is_active is not None:
            results = [l for l in results if l.is_active == is_active]
        return sorted(results, key=lambda l: l.name)

    async def clear(self):
        await self._store.clear()


class SqlCameraRepository(CameraRepository):
    """Durable camera repository backed by the generic document store."""

    def __init__(self):
        from app.db import DocumentStore
        self._store = DocumentStore("camera")

    async def create(self, camera: Camera) -> Camera:
        await self._store.upsert(str(camera.id), camera.model_dump(mode="json"))
        return camera

    async def get_by_id(self, camera_id: UUID) -> Optional[Camera]:
        data = await self._store.get(str(camera_id))
        return Camera(**{k: v for k, v in data.items() if k != "_seq"}) if data else None

    async def get_by_name(self, name: str) -> Optional[Camera]:
        for data in await self._store.list_all():
            cam = Camera(**{k: v for k, v in data.items() if k != "_seq"})
            if cam.name.lower() == name.lower():
                return cam
        return None

    async def update(self, camera: Camera) -> Camera:
        camera.updated_at = datetime.now(timezone.utc)
        await self._store.upsert(str(camera.id), camera.model_dump(mode="json"))
        return camera

    async def delete(self, camera_id: UUID) -> None:
        await self._store.delete(str(camera_id))

    async def list_all(
        self,
        status: Optional[CameraStatus] = None,
        location_id: Optional[UUID] = None,
    ) -> List[Camera]:
        results = [
            Camera(**{k: v for k, v in d.items() if k != "_seq"})
            for d in await self._store.list_all()
        ]
        if status is not None:
            results = [c for c in results if c.status == status]
        if location_id is not None:
            results = [c for c in results if c.location_id == location_id]
        return sorted(results, key=lambda c: c.name)

    async def count_by_location(self, location_id: UUID) -> int:
        cameras = await self.list_all()
        return sum(1 for c in cameras if c.location_id == location_id)

    async def clear(self):
        await self._store.clear()
