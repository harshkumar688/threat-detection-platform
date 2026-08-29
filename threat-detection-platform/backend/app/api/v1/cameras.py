"""
Camera Router

Endpoints:
- GET    /cameras/            → List all cameras (optional status/location filter)
- POST   /cameras/            → Register new camera (admin)
- GET    /cameras/{id}        → Get camera details
- PUT    /cameras/{id}        → Update camera config (admin)
- DELETE /cameras/{id}        → Remove camera (admin)
- POST   /cameras/{id}/start  → Start stream processing (operator)
- POST   /cameras/{id}/stop   → Stop stream processing (operator)

Wired to the real CameraService (app/cameras), which validates location
references and is the same service the incidents router uses to resolve
a camera's configured location when creating an incident.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, get_current_user, require_admin, require_operator
from app.cameras import (
    CameraCreate,
    CameraService,
    CameraStatus,
    CameraUpdate,
    InMemoryCameraRepository,
)
from app.cameras.exceptions import (
    CameraNotFoundError,
    DuplicateCameraNameError,
    LocationNotFoundError,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.camera import CameraResponse
from app.schemas.camera import CameraCreate as CameraCreateSchema
from app.schemas.camera import CameraUpdate as CameraUpdateSchema

router = APIRouter(prefix="/cameras", tags=["Cameras"])

# Service instance (in production, injected via Depends with a DB session).
# Shares the location repository with the locations router so both operate
# on the same underlying location store.
_camera_repo = InMemoryCameraRepository()


def _build_camera_service() -> CameraService:
    from app.api.v1.locations import _location_repo
    return CameraService(_camera_repo, _location_repo)


_camera_service = _build_camera_service()


def _camera_to_response(camera) -> CameraResponse:
    return CameraResponse(
        id=str(camera.id),
        name=camera.name,
        location_id=str(camera.location_id) if camera.location_id else None,
        stream_url=camera.stream_url,
        stream_type=camera.stream_type.value,
        target_fps=camera.target_fps,
        resolution_width=camera.resolution_width,
        resolution_height=camera.resolution_height,
        status=camera.status.value,
        is_enabled=camera.is_enabled,
        last_online_at=camera.last_online_at.isoformat() if camera.last_online_at else None,
        error_message=camera.error_message,
        metadata=camera.metadata,
        created_at=camera.created_at.isoformat(),
    )


@router.get(
    "/",
    response_model=list[CameraResponse],
    summary="List all cameras",
    description="Returns all registered cameras with their current status. Optional filters by status and location.",
)
async def list_cameras(
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    location_id: Optional[str] = Query(default=None, description="Filter by linked location ID"),
    user: CurrentUser = Depends(get_current_user),
):
    """List all cameras. Accessible by all authenticated users."""
    cam_status = None
    if status_filter:
        try:
            cam_status = CameraStatus(status_filter)
        except ValueError:
            pass

    loc_uuid = None
    if location_id:
        try:
            loc_uuid = UUID(location_id)
        except ValueError:
            pass

    cameras = await _camera_service.list_cameras(status=cam_status, location_id=loc_uuid)
    return [_camera_to_response(c) for c in cameras]


@router.post(
    "/",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new camera",
    description="Add a new camera to the system, optionally linked to an existing location. Requires admin role.",
)
async def create_camera(body: CameraCreateSchema, user: CurrentUser = Depends(require_admin)):
    """Register a new camera. Admin only."""
    location_uuid = UUID(body.location_id) if body.location_id else None

    try:
        camera = await _camera_service.create_camera(
            CameraCreate(
                name=body.name,
                location_id=location_uuid,
                stream_url=body.stream_url,
                stream_type=body.stream_type,
                target_fps=body.target_fps,
                is_enabled=body.is_enabled,
                metadata=body.metadata,
            )
        )
    except DuplicateCameraNameError as e:
        raise ConflictError(str(e))
    except LocationNotFoundError:
        raise NotFoundError("Location", body.location_id)

    return _camera_to_response(camera)


@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Get camera details",
    description="Retrieve details for a specific camera.",
)
async def get_camera(camera_id: str, user: CurrentUser = Depends(get_current_user)):
    """Get a single camera by ID."""
    try:
        camera = await _camera_service.get_camera(UUID(camera_id))
    except (CameraNotFoundError, ValueError):
        raise NotFoundError("Camera", camera_id)

    return _camera_to_response(camera)


@router.put(
    "/{camera_id}",
    response_model=CameraResponse,
    summary="Update camera configuration",
    description="Update camera settings, including reassigning its location. Requires admin role.",
)
async def update_camera(
    camera_id: str,
    body: CameraUpdateSchema,
    user: CurrentUser = Depends(require_admin),
):
    """Update a camera's configuration. Admin only."""
    try:
        camera_uuid = UUID(camera_id)
    except ValueError:
        raise NotFoundError("Camera", camera_id)

    update_dict = body.model_dump(exclude_unset=True)
    if "location_id" in update_dict and update_dict["location_id"]:
        update_dict["location_id"] = UUID(update_dict["location_id"])

    try:
        camera = await _camera_service.update_camera(camera_uuid, CameraUpdate(**update_dict))
    except CameraNotFoundError:
        raise NotFoundError("Camera", camera_id)
    except DuplicateCameraNameError as e:
        raise ConflictError(str(e))
    except LocationNotFoundError:
        raise NotFoundError("Location", str(update_dict.get("location_id")))

    return _camera_to_response(camera)


@router.delete(
    "/{camera_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete camera",
    description="Remove a camera from the system. Requires admin role.",
)
async def delete_camera(camera_id: str, user: CurrentUser = Depends(require_admin)):
    """Delete a camera. Admin only."""
    try:
        await _camera_service.delete_camera(UUID(camera_id))
    except (CameraNotFoundError, ValueError):
        raise NotFoundError("Camera", camera_id)


@router.post(
    "/{camera_id}/start",
    response_model=CameraResponse,
    summary="Start stream processing",
    description="Begin detection processing on this camera. Requires operator role.",
)
async def start_camera(camera_id: str, user: CurrentUser = Depends(require_operator)):
    """Start detection processing on a camera."""
    try:
        camera = await _camera_service.start_stream(UUID(camera_id))
    except (CameraNotFoundError, ValueError):
        raise NotFoundError("Camera", camera_id)

    return _camera_to_response(camera)


@router.post(
    "/{camera_id}/stop",
    response_model=CameraResponse,
    summary="Stop stream processing",
    description="Stop detection processing on this camera. Requires operator role.",
)
async def stop_camera(camera_id: str, user: CurrentUser = Depends(require_operator)):
    """Stop detection processing on a camera."""
    try:
        camera = await _camera_service.stop_stream(UUID(camera_id))
    except (CameraNotFoundError, ValueError):
        raise NotFoundError("Camera", camera_id)

    return _camera_to_response(camera)
