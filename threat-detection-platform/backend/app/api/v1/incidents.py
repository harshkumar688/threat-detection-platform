"""
Incident Router

Endpoints:
- GET    /incidents/              → List incidents (paginated, filterable)
- POST   /incidents/              → Create manual incident (operator)
- GET    /incidents/{id}          → Get incident details
- PUT    /incidents/{id}/status   → Update incident status (operator)
- GET    /incidents/{id}/audit    → Get incident audit log (admin)
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    CurrentUser,
    get_current_user,
    get_pagination,
    require_admin,
    require_operator,
)
from app.core.exceptions import InvalidStateTransitionError, NotFoundError
from app.incidents import (
    IncidentCreate,
    IncidentService,
    IncidentStatus,
    IncidentUpdate,
    InMemoryIncidentRepository,
    SqlIncidentRepository,
)
from app.incidents.exceptions import (
    DuplicateIncidentError,
    IncidentNotFoundError,
    InvalidTransitionError,
)
from app.schemas.base import PaginatedResponse, PaginationMeta, PaginationParams
from app.schemas.incident import (
    IncidentCreateRequest,
    IncidentListResponse,
    IncidentResponse,
    IncidentStatusUpdate,
)

router = APIRouter(prefix="/incidents", tags=["Incidents"])

# Repository selection:
#   USE_DATABASE=false -> in-memory (fast, ephemeral; used by the test suite)
#   otherwise          -> durable SQL store (SQLite by default) so incidents
#                         survive backend restarts.
import os as _os


def _build_incident_repo():
    if _os.getenv("USE_DATABASE", "true").lower() in ("0", "false", "no"):
        return InMemoryIncidentRepository()
    return SqlIncidentRepository()


_repo = _build_incident_repo()
_service = IncidentService(_repo)


async def _get_alert_service():
    """
    Lazily import the alert service.

    Deferred to avoid a hard import-time dependency between the incidents
    and alerts routers — alert creation is best-effort: if it fails, the
    incident is still created successfully.
    """
    from app.api.v1.alerts import _service as alert_service
    return alert_service


async def _get_camera_service():
    """
    Lazily import the camera service.

    Deferred for the same reason as _get_alert_service: avoids a hard
    import-time coupling between routers that are otherwise independent.
    """
    from app.api.v1.cameras import _camera_service
    return _camera_service


@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="List incidents",
    description="Paginated list of incidents with optional filtering by status, camera, risk level.",
)
async def list_incidents(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    camera_id: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
    pagination: PaginationParams = Depends(get_pagination),
    user: CurrentUser = Depends(get_current_user),
):
    """List incidents with filtering and pagination."""
    inc_status = None
    if status_filter:
        try:
            inc_status = IncidentStatus(status_filter)
        except ValueError:
            pass

    incidents = await _service.list_incidents(
        status=inc_status,
        camera_id=camera_id,
        risk_level=risk_level,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    total = await _service.count_incidents(status=inc_status, camera_id=camera_id)
    total_pages = (total + pagination.page_size - 1) // pagination.page_size if total > 0 else 0

    data = [
        IncidentListResponse(
            id=str(i.id),
            incident_number=i.incident_number,
            camera_id=i.camera_id,
            threat_type=i.threat_type,
            risk_score=i.risk_score,
            risk_level=i.risk_level,
            status=i.status.value,
            location_name=i.location_name,
            latitude=i.latitude,
            longitude=i.longitude,
            created_at=i.created_at.isoformat(),
        ).model_dump()
        for i in incidents
    ]

    return PaginatedResponse(
        data=data,
        meta=PaginationMeta(
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total,
            total_pages=total_pages,
        ),
    )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create manual incident",
    description="Manually create an incident. Requires operator role.",
)
async def create_incident(
    body: IncidentCreateRequest,
    user: CurrentUser = Depends(require_operator),
):
    """
    Create a manual incident (operator-initiated).

    The referenced camera must be registered (see /cameras). The incident
    captures a snapshot of that camera's configured location (name,
    building, zone, latitude/longitude) at creation time, so the record
    remains accurate even if the camera is later moved or reassigned.

    A confirmed incident automatically attempts to raise an alert via
    AlertService — subject to severity threshold and duplicate-prevention
    rules. Alert creation failures are logged but never block the incident
    response; the incident is the source of truth and always succeeds.
    """
    from uuid import UUID

    from app.cameras.exceptions import CameraNotFoundError

    camera_service = await _get_camera_service()
    try:
        camera = await camera_service.get_camera(UUID(body.camera_id))
    except (CameraNotFoundError, ValueError):
        raise NotFoundError("Camera", body.camera_id)

    location_snapshot = await camera_service.resolve_location_snapshot(camera.id)

    incident = await _service.create_incident(
        IncidentCreate(
            camera_id=body.camera_id,
            threat_type=body.threat_type,
            confidence=0.0,  # Manual — no detection confidence
            risk_score=50.0,  # Default manual score
            risk_level=body.risk_level,
            description=body.description,
            location_id=location_snapshot.location_id,
            location_name=location_snapshot.location_name,
            building=location_snapshot.building,
            zone=location_snapshot.zone,
            latitude=location_snapshot.latitude,
            longitude=location_snapshot.longitude,
        )
    )

    await _raise_alert_for_incident(incident)

    return _incident_to_response(incident)


async def _raise_alert_for_incident(incident) -> None:
    """
    Attempt to create an alert for a newly confirmed incident.

    This is the integration point between incident creation (this module)
    and alert management (app/alerts). It is intentionally best-effort:
    AlertService already enforces severity thresholds and duplicate
    prevention internally (returning None rather than raising in the
    common "no alert needed" cases), and any unexpected error here is
    logged, never re-raised, so a notification-layer problem can never
    prevent an incident from being recorded.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        alert_service = await _get_alert_service()
        await alert_service.create_from_incident(
            incident_id=incident.id,
            camera_id=incident.camera_id,
            risk_level=incident.risk_level,
            threat_type=incident.threat_type,
            risk_score=incident.risk_score,
            location_name=incident.location_name,
        )
    except Exception:
        logger.exception("Failed to raise alert for incident %s", incident.id)


@router.get(
    "/{incident_id}",
    summary="Get incident details",
    description="Retrieve full incident details including metadata.",
)
async def get_incident(
    incident_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a single incident by ID."""
    try:
        from uuid import UUID
        incident = await _service.get_incident(UUID(incident_id))
    except IncidentNotFoundError:
        raise NotFoundError("Incident", incident_id)
    except ValueError:
        raise NotFoundError("Incident", incident_id)

    return _incident_to_response(incident)


@router.put(
    "/{incident_id}/status",
    summary="Update incident status",
    description="Transition incident to a new state. Requires operator role.",
)
async def update_incident_status(
    incident_id: str,
    body: IncidentStatusUpdate,
    user: CurrentUser = Depends(require_operator),
):
    """Update incident status (ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE)."""
    try:
        from uuid import UUID
        new_status = IncidentStatus(body.status)
        incident = await _service.update_status(
            UUID(incident_id),
            IncidentUpdate(status=new_status, user_id=user.user_id, notes=body.notes),
        )
    except IncidentNotFoundError:
        raise NotFoundError("Incident", incident_id)
    except InvalidTransitionError as e:
        raise InvalidStateTransitionError(e.from_status.value, e.to_status.value)
    except ValueError:
        raise NotFoundError("Incident", incident_id)

    return _incident_to_response(incident)


@router.get(
    "/{incident_id}/audit",
    summary="Get incident audit log",
    description="Full audit trail for an incident. Requires admin role.",
)
async def get_incident_audit(
    incident_id: str,
    user: CurrentUser = Depends(require_admin),
):
    """Get audit log for an incident. Admin only."""
    try:
        from uuid import UUID
        log = await _service.get_audit_log(UUID(incident_id))
    except IncidentNotFoundError:
        raise NotFoundError("Incident", incident_id)

    return {
        "incident_id": incident_id,
        "entries": [
            {
                "id": str(e.id),
                "action": e.action,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "user_id": e.user_id,
                "notes": e.notes,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in log
        ],
    }


def _incident_to_response(incident) -> dict:
    """Convert incident model to response dict."""
    return IncidentResponse(
        id=str(incident.id),
        incident_number=incident.incident_number,
        camera_id=incident.camera_id,
        threat_type=incident.threat_type,
        confidence=incident.confidence,
        risk_score=incident.risk_score,
        risk_level=incident.risk_level,
        status=incident.status.value,
        track_id=incident.track_id,
        location_id=str(incident.location_id) if incident.location_id else None,
        location_name=incident.location_name,
        building=incident.building,
        zone=incident.zone,
        latitude=incident.latitude,
        longitude=incident.longitude,
        weapon_count=incident.weapon_count,
        frames_confirmed=incident.frames_confirmed,
        description=incident.description,
        acknowledged_by=incident.acknowledged_by,
        acknowledged_at=incident.acknowledged_at.isoformat() if incident.acknowledged_at else None,
        resolved_by=incident.resolved_by,
        resolved_at=incident.resolved_at.isoformat() if incident.resolved_at else None,
        resolution_notes=incident.resolution_notes,
        created_at=incident.created_at.isoformat(),
        updated_at=incident.updated_at.isoformat(),
    ).model_dump()
