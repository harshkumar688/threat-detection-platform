"""
Location Router

Endpoints:
- GET    /locations/            → List all locations
- POST   /locations/            → Create new location (admin)
- GET    /locations/{id}        → Get location details
- PUT    /locations/{id}        → Update location (admin)
- DELETE /locations/{id}        → Delete location (admin, blocked if in use)

Wired to the real LocationService (app/cameras.LocationService). The
underlying location repository is shared with the cameras router so both
operate on the same store.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, get_current_user, require_admin
from app.cameras import (
    InMemoryLocationRepository,
    LocationCreate,
    LocationService,
    LocationUpdate,
)
from app.cameras.exceptions import (
    DuplicateLocationNameError,
    LocationInUseError,
    LocationNotFoundError,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.camera import LocationCreate as LocationCreateSchema
from app.schemas.camera import LocationResponse
from app.schemas.camera import LocationUpdate as LocationUpdateSchema

router = APIRouter(prefix="/locations", tags=["Locations"])

# Shared repository instance — imported by app/api/v1/cameras.py so both
# routers (and CameraService's location validation) see the same data.
_location_repo = InMemoryLocationRepository()
_location_service = LocationService(_location_repo)


def _location_to_response(location) -> LocationResponse:
    return LocationResponse(
        id=str(location.id),
        name=location.name,
        building=location.building,
        floor=location.floor,
        zone=location.zone,
        description=location.description,
        latitude=location.latitude,
        longitude=location.longitude,
        is_active=location.is_active,
        created_at=location.created_at.isoformat(),
    )


@router.get(
    "/",
    response_model=list[LocationResponse],
    summary="List all locations",
    description="Returns all registered physical locations.",
)
async def list_locations(
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    user: CurrentUser = Depends(get_current_user),
):
    """List all locations. Accessible by all authenticated users."""
    locations = await _location_service.list_locations(is_active=is_active)
    return [_location_to_response(l) for l in locations]


@router.post(
    "/",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new location",
    description="Register a new physical location. Requires admin role.",
)
async def create_location(body: LocationCreateSchema, user: CurrentUser = Depends(require_admin)):
    """Create a new location. Admin only."""
    try:
        location = await _location_service.create_location(
            LocationCreate(
                name=body.name,
                building=body.building,
                floor=body.floor,
                zone=body.zone,
                description=body.description,
                latitude=body.latitude,
                longitude=body.longitude,
            )
        )
    except DuplicateLocationNameError as e:
        raise ConflictError(str(e))

    return _location_to_response(location)


@router.get(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Get location details",
    description="Retrieve details for a specific location.",
)
async def get_location(location_id: str, user: CurrentUser = Depends(get_current_user)):
    """Get a single location by ID."""
    try:
        location = await _location_service.get_location(UUID(location_id))
    except (LocationNotFoundError, ValueError):
        raise NotFoundError("Location", location_id)

    return _location_to_response(location)


@router.put(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Update location",
    description="Update a location's details, including coordinates. Requires admin role.",
)
async def update_location(
    location_id: str,
    body: LocationUpdateSchema,
    user: CurrentUser = Depends(require_admin),
):
    """Update a location. Admin only."""
    try:
        location_uuid = UUID(location_id)
    except ValueError:
        raise NotFoundError("Location", location_id)

    try:
        location = await _location_service.update_location(
            location_uuid, LocationUpdate(**body.model_dump(exclude_unset=True))
        )
    except LocationNotFoundError:
        raise NotFoundError("Location", location_id)
    except DuplicateLocationNameError as e:
        raise ConflictError(str(e))

    return _location_to_response(location)


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete location",
    description=(
        "Remove a location. Requires admin role. Rejected with 409 Conflict "
        "if any camera is still linked to this location — reassign or remove "
        "those cameras first."
    ),
)
async def delete_location(location_id: str, user: CurrentUser = Depends(require_admin)):
    """Delete a location. Admin only. Fails if cameras still reference it."""
    from app.api.v1.cameras import _camera_repo

    try:
        location_uuid = UUID(location_id)
    except ValueError:
        raise NotFoundError("Location", location_id)

    try:
        await _location_service.delete_location(location_uuid, _camera_repo)
    except LocationNotFoundError:
        raise NotFoundError("Location", location_id)
    except LocationInUseError as e:
        raise ConflictError(str(e))
