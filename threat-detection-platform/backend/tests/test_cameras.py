"""
Camera & Location Service Unit Tests

Tests:
- Location creation, update, deletion (with delete-safety check)
- Camera creation, update, deletion, lifecycle (start/stop/error)
- Location reference validation (camera creation rejects unknown location_id)
- Duplicate name prevention for both cameras and locations
- LocationSnapshot resolution (used by incident creation)
"""

from uuid import uuid4

import pytest

from app.cameras import (
    Camera,
    CameraCreate,
    CameraService,
    CameraStatus,
    CameraUpdate,
    InMemoryCameraRepository,
    InMemoryLocationRepository,
    Location,
    LocationCreate,
    LocationService,
    LocationUpdate,
    StreamType,
)
from app.cameras.exceptions import (
    CameraNotFoundError,
    DuplicateCameraNameError,
    DuplicateLocationNameError,
    LocationInUseError,
    LocationNotFoundError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def location_repo():
    return InMemoryLocationRepository()


@pytest.fixture
def camera_repo():
    return InMemoryCameraRepository()


@pytest.fixture
def location_service(location_repo):
    return LocationService(location_repo)


@pytest.fixture
def camera_service(camera_repo, location_repo):
    return CameraService(camera_repo, location_repo)


# =============================================================================
# Location Service
# =============================================================================

class TestLocationCreation:
    @pytest.mark.asyncio
    async def test_create_location_with_coordinates(self, location_service):
        location = await location_service.create_location(
            LocationCreate(
                name="Main Entrance Lobby",
                building="Block A",
                floor="Ground",
                zone="Entry Zone",
                latitude=28.6139,
                longitude=77.2090,
            )
        )
        assert location.name == "Main Entrance Lobby"
        assert location.latitude == 28.6139
        assert location.longitude == 77.2090
        assert location.has_coordinates is True
        assert location.is_active is True

    @pytest.mark.asyncio
    async def test_create_location_without_coordinates(self, location_service):
        """Indoor locations may have no meaningful GPS coordinate."""
        location = await location_service.create_location(
            LocationCreate(name="Server Room", building="Block B", floor="2")
        )
        assert location.latitude is None
        assert location.longitude is None
        assert location.has_coordinates is False

    @pytest.mark.asyncio
    async def test_duplicate_location_name_rejected(self, location_service):
        await location_service.create_location(LocationCreate(name="Parking Lot"))
        with pytest.raises(DuplicateLocationNameError):
            await location_service.create_location(LocationCreate(name="Parking Lot"))

    @pytest.mark.asyncio
    async def test_duplicate_name_case_insensitive(self, location_service):
        await location_service.create_location(LocationCreate(name="Lobby"))
        with pytest.raises(DuplicateLocationNameError):
            await location_service.create_location(LocationCreate(name="LOBBY"))

    def test_invalid_latitude_rejected(self):
        with pytest.raises(Exception):
            LocationCreate(name="Bad Coords", latitude=200.0)

    def test_invalid_longitude_rejected(self):
        with pytest.raises(Exception):
            LocationCreate(name="Bad Coords", longitude=-200.0)


class TestLocationUpdate:
    @pytest.mark.asyncio
    async def test_update_coordinates(self, location_service):
        location = await location_service.create_location(LocationCreate(name="Rooftop"))
        updated = await location_service.update_location(
            location.id, LocationUpdate(latitude=12.34, longitude=56.78)
        )
        assert updated.latitude == 12.34
        assert updated.longitude == 56.78

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises(self, location_service):
        with pytest.raises(LocationNotFoundError):
            await location_service.update_location(uuid4(), LocationUpdate(name="X"))

    @pytest.mark.asyncio
    async def test_rename_to_existing_name_rejected(self, location_service):
        await location_service.create_location(LocationCreate(name="A"))
        loc_b = await location_service.create_location(LocationCreate(name="B"))

        with pytest.raises(DuplicateLocationNameError):
            await location_service.update_location(loc_b.id, LocationUpdate(name="A"))

    @pytest.mark.asyncio
    async def test_deactivate_location(self, location_service):
        location = await location_service.create_location(LocationCreate(name="Old Wing"))
        updated = await location_service.update_location(location.id, LocationUpdate(is_active=False))
        assert updated.is_active is False


class TestLocationDeletion:
    @pytest.mark.asyncio
    async def test_delete_unused_location(self, location_service, camera_repo):
        location = await location_service.create_location(LocationCreate(name="Empty Room"))
        await location_service.delete_location(location.id, camera_repo)

        with pytest.raises(LocationNotFoundError):
            await location_service.get_location(location.id)

    @pytest.mark.asyncio
    async def test_delete_location_in_use_rejected(self, location_service, camera_service, camera_repo):
        location = await location_service.create_location(LocationCreate(name="Busy Room"))
        await camera_service.create_camera(
            CameraCreate(name="Cam1", location_id=location.id, stream_url="rtsp://x/1")
        )

        with pytest.raises(LocationInUseError):
            await location_service.delete_location(location.id, camera_repo)

        # Location must still exist — deletion never partially succeeds
        still_there = await location_service.get_location(location.id)
        assert still_there is not None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, location_service, camera_repo):
        with pytest.raises(LocationNotFoundError):
            await location_service.delete_location(uuid4(), camera_repo)


# =============================================================================
# Camera Service
# =============================================================================

class TestCameraCreation:
    @pytest.mark.asyncio
    async def test_create_camera_without_location(self, camera_service):
        camera = await camera_service.create_camera(
            CameraCreate(name="Standalone Cam", stream_url="rtsp://192.168.1.10/stream")
        )
        assert camera.name == "Standalone Cam"
        assert camera.location_id is None
        assert camera.status == CameraStatus.OFFLINE
        assert camera.stream_type == StreamType.RTSP

    @pytest.mark.asyncio
    async def test_create_camera_with_valid_location(self, camera_service, location_service):
        location = await location_service.create_location(LocationCreate(name="Lobby"))
        camera = await camera_service.create_camera(
            CameraCreate(name="Lobby Cam", location_id=location.id, stream_url="rtsp://x/1")
        )
        assert camera.location_id == location.id

    @pytest.mark.asyncio
    async def test_create_camera_with_invalid_location_rejected(self, camera_service):
        with pytest.raises(LocationNotFoundError):
            await camera_service.create_camera(
                CameraCreate(name="Ghost Cam", location_id=uuid4(), stream_url="rtsp://x/1")
            )

    @pytest.mark.asyncio
    async def test_duplicate_camera_name_rejected(self, camera_service):
        await camera_service.create_camera(CameraCreate(name="Cam A", stream_url="rtsp://x/1"))
        with pytest.raises(DuplicateCameraNameError):
            await camera_service.create_camera(CameraCreate(name="Cam A", stream_url="rtsp://x/2"))

    @pytest.mark.asyncio
    async def test_camera_defaults(self, camera_service):
        camera = await camera_service.create_camera(
            CameraCreate(name="Defaults Cam", stream_url="rtsp://x/1")
        )
        assert camera.target_fps == 15
        assert camera.is_enabled is True
        assert camera.metadata == {}


class TestCameraUpdate:
    @pytest.mark.asyncio
    async def test_update_stream_url(self, camera_service):
        camera = await camera_service.create_camera(
            CameraCreate(name="Update Cam", stream_url="rtsp://old/1")
        )
        updated = await camera_service.update_camera(
            camera.id, CameraUpdate(stream_url="rtsp://new/1")
        )
        assert updated.stream_url == "rtsp://new/1"

    @pytest.mark.asyncio
    async def test_reassign_location(self, camera_service, location_service):
        loc_a = await location_service.create_location(LocationCreate(name="Loc A"))
        loc_b = await location_service.create_location(LocationCreate(name="Loc B"))
        camera = await camera_service.create_camera(
            CameraCreate(name="Movable Cam", location_id=loc_a.id, stream_url="rtsp://x/1")
        )

        updated = await camera_service.update_camera(camera.id, CameraUpdate(location_id=loc_b.id))
        assert updated.location_id == loc_b.id

    @pytest.mark.asyncio
    async def test_reassign_to_invalid_location_rejected(self, camera_service):
        camera = await camera_service.create_camera(
            CameraCreate(name="Cam", stream_url="rtsp://x/1")
        )
        with pytest.raises(LocationNotFoundError):
            await camera_service.update_camera(camera.id, CameraUpdate(location_id=uuid4()))

    @pytest.mark.asyncio
    async def test_update_nonexistent_camera_raises(self, camera_service):
        with pytest.raises(CameraNotFoundError):
            await camera_service.update_camera(uuid4(), CameraUpdate(name="X"))

    @pytest.mark.asyncio
    async def test_rename_to_existing_name_rejected(self, camera_service):
        await camera_service.create_camera(CameraCreate(name="Cam1", stream_url="rtsp://x/1"))
        cam2 = await camera_service.create_camera(CameraCreate(name="Cam2", stream_url="rtsp://x/2"))

        with pytest.raises(DuplicateCameraNameError):
            await camera_service.update_camera(cam2.id, CameraUpdate(name="Cam1"))


class TestCameraLifecycle:
    @pytest.mark.asyncio
    async def test_start_stream_sets_processing(self, camera_service):
        camera = await camera_service.create_camera(
            CameraCreate(name="Cam", stream_url="rtsp://x/1")
        )
        started = await camera_service.start_stream(camera.id)
        assert started.status == CameraStatus.PROCESSING
        assert started.last_online_at is not None
        assert started.error_message is None

    @pytest.mark.asyncio
    async def test_stop_stream_sets_offline(self, camera_service):
        camera = await camera_service.create_camera(
            CameraCreate(name="Cam", stream_url="rtsp://x/1")
        )
        await camera_service.start_stream(camera.id)
        stopped = await camera_service.stop_stream(camera.id)
        assert stopped.status == CameraStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_report_error_sets_error_status(self, camera_service):
        camera = await camera_service.create_camera(
            CameraCreate(name="Cam", stream_url="rtsp://x/1")
        )
        errored = await camera_service.report_error(camera.id, "Connection timeout")
        assert errored.status == CameraStatus.ERROR
        assert errored.error_message == "Connection timeout"

    @pytest.mark.asyncio
    async def test_start_nonexistent_camera_raises(self, camera_service):
        with pytest.raises(CameraNotFoundError):
            await camera_service.start_stream(uuid4())


class TestCameraDeletion:
    @pytest.mark.asyncio
    async def test_delete_camera(self, camera_service):
        camera = await camera_service.create_camera(
            CameraCreate(name="Cam", stream_url="rtsp://x/1")
        )
        await camera_service.delete_camera(camera.id)

        with pytest.raises(CameraNotFoundError):
            await camera_service.get_camera(camera.id)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, camera_service):
        with pytest.raises(CameraNotFoundError):
            await camera_service.delete_camera(uuid4())


class TestCameraListing:
    @pytest.mark.asyncio
    async def test_filter_by_status(self, camera_service):
        cam1 = await camera_service.create_camera(CameraCreate(name="Cam1", stream_url="rtsp://x/1"))
        await camera_service.create_camera(CameraCreate(name="Cam2", stream_url="rtsp://x/2"))
        await camera_service.start_stream(cam1.id)

        processing = await camera_service.list_cameras(status=CameraStatus.PROCESSING)
        assert len(processing) == 1
        assert processing[0].id == cam1.id

    @pytest.mark.asyncio
    async def test_filter_by_location(self, camera_service, location_service):
        loc = await location_service.create_location(LocationCreate(name="Filter Loc"))
        await camera_service.create_camera(
            CameraCreate(name="Linked Cam", location_id=loc.id, stream_url="rtsp://x/1")
        )
        await camera_service.create_camera(CameraCreate(name="Unlinked Cam", stream_url="rtsp://x/2"))

        linked = await camera_service.list_cameras(location_id=loc.id)
        assert len(linked) == 1
        assert linked[0].name == "Linked Cam"


# =============================================================================
# Location Snapshot Resolution (used by incident creation)
# =============================================================================

class TestLocationSnapshotResolution:
    @pytest.mark.asyncio
    async def test_resolve_snapshot_for_camera_with_location(self, camera_service, location_service):
        location = await location_service.create_location(
            LocationCreate(name="Snapshot Loc", building="B1", zone="Z1", latitude=1.0, longitude=2.0)
        )
        camera = await camera_service.create_camera(
            CameraCreate(name="Snap Cam", location_id=location.id, stream_url="rtsp://x/1")
        )

        snapshot = await camera_service.resolve_location_snapshot(camera.id)
        assert snapshot.location_id == location.id
        assert snapshot.location_name == "Snapshot Loc"
        assert snapshot.building == "B1"
        assert snapshot.zone == "Z1"
        assert snapshot.latitude == 1.0
        assert snapshot.longitude == 2.0

    @pytest.mark.asyncio
    async def test_resolve_snapshot_for_camera_without_location(self, camera_service):
        camera = await camera_service.create_camera(
            CameraCreate(name="No Loc Cam", stream_url="rtsp://x/1")
        )
        snapshot = await camera_service.resolve_location_snapshot(camera.id)
        assert snapshot.location_id is None
        assert snapshot.location_name == ""

    @pytest.mark.asyncio
    async def test_resolve_snapshot_for_nonexistent_camera_returns_empty(self, camera_service):
        """Must never raise — incident creation should not fail just because
        location resolution encountered a missing camera."""
        snapshot = await camera_service.resolve_location_snapshot(uuid4())
        assert snapshot.location_id is None
        assert snapshot.location_name == ""

    @pytest.mark.asyncio
    async def test_snapshot_immune_to_later_location_rename(self, camera_service, location_service, location_repo):
        """
        A snapshot taken at one point in time must not change even if the
        underlying Location is later renamed — this is exactly the guarantee
        incident records rely on.
        """
        location = await location_service.create_location(LocationCreate(name="Original Name"))
        camera = await camera_service.create_camera(
            CameraCreate(name="Cam", location_id=location.id, stream_url="rtsp://x/1")
        )

        snapshot_before = await camera_service.resolve_location_snapshot(camera.id)
        assert snapshot_before.location_name == "Original Name"

        await location_service.update_location(location.id, LocationUpdate(name="Renamed Location"))

        # A NEW resolution reflects the rename (this is expected — only a
        # previously taken snapshot object is immutable, not live lookups)
        snapshot_after = await camera_service.resolve_location_snapshot(camera.id)
        assert snapshot_after.location_name == "Renamed Location"

        # But the earlier snapshot object itself is untouched
        assert snapshot_before.location_name == "Original Name"
