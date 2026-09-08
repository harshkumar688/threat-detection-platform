"""
Alert Router

Endpoints:
- GET  /alerts/                    → List alerts (paginated, filterable)
- GET  /alerts/count               → Unread/unacknowledged counts for dashboard badge
- GET  /alerts/{id}                → Get alert details
- PUT  /alerts/{id}/acknowledge     → Acknowledge an alert (operator)
- PUT  /alerts/{id}/dismiss         → Dismiss an alert (operator)
- GET  /alerts/{id}/notifications   → Notification delivery history for an alert (admin)

Wired to the real AlertService (app/alerts), which enforces severity
thresholds, duplicate prevention, and dispatches notifications through
configurable channels — never a disconnected in-memory placeholder.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.alerts import (
    AlertAcknowledge,
    AlertConfig,
    AlertDismiss,
    AlertService,
    AlertStatus,
    InMemoryAlertRepository,
    SqlAlertRepository,
    NotificationDispatcher,
)
from app.alerts.exceptions import AlertNotFoundError, InvalidAlertTransitionError
from app.alerts.providers import build_providers_from_config
from app.api.deps import (
    CurrentUser,
    get_current_user,
    get_pagination,
    require_admin,
    require_operator,
)
from app.core.exceptions import InvalidStateTransitionError, NotFoundError
from app.schemas.alert import (
    AlertAcknowledgeRequest,
    AlertCountResponse,
    AlertDismissRequest,
    AlertResponse,
    NotificationLogResponse,
)
from app.schemas.base import PaginatedResponse, PaginationMeta, PaginationParams

router = APIRouter(prefix="/alerts", tags=["Alerts"])

import os as _os
_config = AlertConfig()
_repo = (
    InMemoryAlertRepository()
    if _os.getenv("USE_DATABASE", "true").lower() in ("0", "false", "no")
    else SqlAlertRepository()
)
_providers = build_providers_from_config(_config)
_dispatcher = NotificationDispatcher(_config, _providers, _repo)
_service = AlertService(_config, _repo, _dispatcher)


def _alert_to_response(alert) -> AlertResponse:
    return AlertResponse(
        id=str(alert.id),
        alert_number=alert.alert_number,
        incident_id=str(alert.incident_id),
        camera_id=alert.camera_id,
        severity=alert.severity.value,
        title=alert.title,
        message=alert.message,
        status=alert.status.value,
        is_acknowledged=alert.is_acknowledged,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        acknowledgement_notes=alert.acknowledgement_notes,
        dismissed_by=alert.dismissed_by,
        dismissed_at=alert.dismissed_at.isoformat() if alert.dismissed_at else None,
        created_at=alert.created_at.isoformat(),
        updated_at=alert.updated_at.isoformat(),
    )


@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="List alerts",
    description="Paginated list of alerts with optional severity/status filtering.",
)
async def list_alerts(
    severity: Optional[str] = Query(default=None, description="Filter by severity: MEDIUM, HIGH, CRITICAL"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    pagination: PaginationParams = Depends(get_pagination),
    user: CurrentUser = Depends(get_current_user),
):
    """List alerts with pagination and optional filters."""
    alert_status = None
    if status_filter:
        try:
            alert_status = AlertStatus(status_filter)
        except ValueError:
            pass

    alerts = await _service.list_alerts(
        status=alert_status,
        severity=severity,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    total = await _service.count_alerts(status=alert_status, severity=severity)
    total_pages = (total + pagination.page_size - 1) // pagination.page_size if total > 0 else 0

    data = [_alert_to_response(a).model_dump() for a in alerts]

    return PaginatedResponse(
        data=data,
        meta=PaginationMeta(
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/count",
    response_model=AlertCountResponse,
    summary="Alert counts",
    description="Get counts of unacknowledged alerts for the dashboard badge.",
)
async def get_alert_counts(user: CurrentUser = Depends(get_current_user)):
    """Get alert counts for dashboard badges, computed from real alert records."""
    pending = await _service.count_alerts(status=AlertStatus.PENDING)
    dispatched = await _service.count_alerts(status=AlertStatus.DISPATCHED)
    total_unacknowledged = pending + dispatched

    by_severity = {}
    for sev in ("CRITICAL", "HIGH", "MEDIUM"):
        pending_sev = await _service.list_alerts(status=AlertStatus.PENDING, severity=sev, limit=10000)
        dispatched_sev = await _service.list_alerts(status=AlertStatus.DISPATCHED, severity=sev, limit=10000)
        count = len(pending_sev) + len(dispatched_sev)
        if count > 0:
            by_severity[sev] = count

    return AlertCountResponse(
        total_unread=total_unacknowledged,
        total_unacknowledged=total_unacknowledged,
        by_severity=by_severity,
    )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Get alert details",
    description="Retrieve full details for a single alert.",
)
async def get_alert(alert_id: str, user: CurrentUser = Depends(get_current_user)):
    """Get a single alert by ID."""
    try:
        alert = await _service.get_alert(UUID(alert_id))
    except (AlertNotFoundError, ValueError):
        raise NotFoundError("Alert", alert_id)

    return _alert_to_response(alert)


@router.put(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Acknowledge alert",
    description="Mark an alert as acknowledged, indicating an operator has reviewed and accepted it as a real threat. Requires operator role.",
)
async def acknowledge_alert(
    alert_id: str,
    body: AlertAcknowledgeRequest,
    user: CurrentUser = Depends(require_operator),
):
    """Acknowledge an alert."""
    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        raise NotFoundError("Alert", alert_id)

    try:
        alert = await _service.acknowledge(
            alert_uuid, AlertAcknowledge(user_id=user.user_id, notes=body.notes)
        )
    except AlertNotFoundError:
        raise NotFoundError("Alert", alert_id)
    except InvalidAlertTransitionError as e:
        raise InvalidStateTransitionError(e.from_status.value, e.to_status.value)

    return _alert_to_response(alert)


@router.put(
    "/{alert_id}/dismiss",
    response_model=AlertResponse,
    summary="Dismiss alert",
    description="Dismiss an alert without treating it as a confirmed threat (e.g., known false alarm). Requires operator role.",
)
async def dismiss_alert(
    alert_id: str,
    body: AlertDismissRequest,
    user: CurrentUser = Depends(require_operator),
):
    """Dismiss an alert."""
    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        raise NotFoundError("Alert", alert_id)

    try:
        alert = await _service.dismiss(
            alert_uuid, AlertDismiss(user_id=user.user_id, reason=body.reason)
        )
    except AlertNotFoundError:
        raise NotFoundError("Alert", alert_id)
    except InvalidAlertTransitionError as e:
        raise InvalidStateTransitionError(e.from_status.value, e.to_status.value)

    return _alert_to_response(alert)


@router.get(
    "/{alert_id}/notifications",
    response_model=list[NotificationLogResponse],
    summary="Notification delivery history",
    description="Full delivery history (all channels, all attempts) for an alert. Requires admin role.",
)
async def get_notification_history(alert_id: str, admin: CurrentUser = Depends(require_admin)):
    """Get notification delivery history for an alert. Admin only."""
    try:
        logs = await _service.get_notification_history(UUID(alert_id))
    except (AlertNotFoundError, ValueError):
        raise NotFoundError("Alert", alert_id)

    return [
        NotificationLogResponse(
            id=str(log.id),
            channel=log.channel.value,
            status=log.status.value,
            attempt_number=log.attempt_number,
            max_attempts=log.max_attempts,
            error_message=log.error_message,
            created_at=log.created_at.isoformat(),
            sent_at=log.sent_at.isoformat() if log.sent_at else None,
            next_retry_at=log.next_retry_at.isoformat() if log.next_retry_at else None,
        )
        for log in logs
    ]
