"""
Alert Service

Business logic layer for alert management:
- Creates alerts from confirmed incidents (with severity threshold + dedupe)
- Dispatches notifications through configured channels via the dispatcher
- Enforces the alert status state machine
- Provides acknowledgement / dismissal
- Provides querying, filtering, and notification history

This service is the single point of entry for all alert operations.
Routers and other modules (e.g., the detection pipeline integration)
call this — never the repository or dispatcher directly.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from .config import AlertConfig
from .dispatcher import NotificationDispatcher
from .exceptions import (
    AlertNotFoundError,
    BelowAlertThresholdError,
    DuplicateAlertError,
    InvalidAlertTransitionError,
)
from .models import (
    Alert,
    AlertAcknowledge,
    AlertCreate,
    AlertDismiss,
    AlertSeverity,
    AlertStatus,
    NotificationLog,
    is_valid_alert_transition,
)
from .repository import AlertRepository

logger = logging.getLogger(__name__)

# Ordered so we can compare "meets minimum severity"
_SEVERITY_ORDER = {
    "LOW": 0,
    AlertSeverity.MEDIUM.value: 1,
    AlertSeverity.HIGH.value: 2,
    AlertSeverity.CRITICAL.value: 3,
}


def risk_level_to_alert_severity(risk_level: str) -> Optional[AlertSeverity]:
    """
    Map an incident risk_level (LOW/MEDIUM/HIGH/CRITICAL) to an AlertSeverity.

    Returns None for LOW — incidents scored LOW never generate alerts.
    """
    try:
        return AlertSeverity(risk_level)
    except ValueError:
        return None


class AlertService:
    """
    Alert management service.

    Usage:
        repo = InMemoryAlertRepository()
        providers = build_providers_from_config(config)
        dispatcher = NotificationDispatcher(config, providers, repo)
        service = AlertService(config, repo, dispatcher)

        # Create from a confirmed incident
        alert = await service.create_from_incident(
            incident_id=incident.id,
            camera_id=incident.camera_id,
            risk_level=incident.risk_level,
            threat_type=incident.threat_type,
            risk_score=incident.risk_score,
            location_name=incident.location_name,
        )

        # Acknowledge
        alert = await service.acknowledge(alert.id, AlertAcknowledge(user_id="op1"))
    """

    def __init__(
        self,
        config: AlertConfig,
        repository: AlertRepository,
        dispatcher: NotificationDispatcher,
    ):
        self._config = config
        self._repo = repository
        self._dispatcher = dispatcher

    async def create_from_incident(
        self,
        incident_id: UUID,
        camera_id: str,
        risk_level: str,
        threat_type: str,
        risk_score: float,
        location_name: str = "",
    ) -> Optional[Alert]:
        """
        Create (and dispatch) an alert from a confirmed incident.

        Enforces:
        - Minimum severity threshold (incidents below threshold produce no alert)
        - Duplicate prevention: at most one active alert per incident, and
          incidents that alerted very recently (within the dedupe window)
          are suppressed even if the previous alert was already resolved

        Returns:
            The created Alert, or None if suppressed by threshold/dedupe.

        Raises:
            Nothing — threshold/dedupe are expected outcomes, not errors.
            Use create_from_incident_strict() if you need exceptions instead.
        """
        severity = risk_level_to_alert_severity(risk_level)
        if severity is None or not self._meets_threshold(risk_level):
            logger.debug(
                "Alert suppressed (below threshold): incident=%s risk_level=%s min=%s",
                incident_id, risk_level, self._config.min_severity_for_alert,
            )
            return None

        if await self._is_duplicate(incident_id):
            logger.info("Alert suppressed (duplicate): incident=%s", incident_id)
            return None

        title, message = self._render_content(threat_type, risk_level, risk_score, camera_id, location_name)

        alert = Alert(
            incident_id=incident_id,
            camera_id=camera_id,
            severity=severity,
            title=title,
            message=message,
            status=AlertStatus.PENDING,
        )
        alert = await self._repo.create(alert)

        logger.info(
            "Alert created: #%d [%s] incident=%s camera=%s",
            alert.alert_number, severity.value, incident_id, camera_id,
        )

        # Dispatch notifications; failures never block alert creation
        await self._dispatcher.dispatch(alert)
        alert.status = AlertStatus.DISPATCHED
        alert = await self._repo.update(alert)

        return alert

    async def create_from_incident_strict(
        self,
        incident_id: UUID,
        camera_id: str,
        risk_level: str,
        threat_type: str,
        risk_score: float,
        location_name: str = "",
    ) -> Alert:
        """
        Same as create_from_incident(), but raises instead of returning None.

        Raises:
            BelowAlertThresholdError: If risk_level is below the configured minimum.
            DuplicateAlertError: If an active/recent alert already exists for the incident.
        """
        severity = risk_level_to_alert_severity(risk_level)
        if severity is None or not self._meets_threshold(risk_level):
            raise BelowAlertThresholdError(risk_level, self._config.min_severity_for_alert)

        if await self._is_duplicate(incident_id):
            raise DuplicateAlertError(incident_id)

        result = await self.create_from_incident(
            incident_id, camera_id, risk_level, threat_type, risk_score, location_name
        )
        assert result is not None  # threshold/dedupe already checked above
        return result

    async def get_alert(self, alert_id: UUID) -> Alert:
        """Retrieve an alert by ID. Raises AlertNotFoundError if not found."""
        alert = await self._repo.get_by_id(alert_id)
        if alert is None:
            raise AlertNotFoundError(alert_id)
        return alert

    async def acknowledge(self, alert_id: UUID, data: AlertAcknowledge) -> Alert:
        """
        Acknowledge an alert.

        Raises:
            AlertNotFoundError: If alert not found.
            InvalidAlertTransitionError: If alert is already in a terminal state.
        """
        alert = await self._repo.get_by_id(alert_id)
        if alert is None:
            raise AlertNotFoundError(alert_id)

        if not is_valid_alert_transition(alert.status, AlertStatus.ACKNOWLEDGED):
            raise InvalidAlertTransitionError(alert.status, AlertStatus.ACKNOWLEDGED)

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.is_acknowledged = True
        alert.acknowledged_by = data.user_id
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledgement_notes = data.notes

        alert = await self._repo.update(alert)

        logger.info("Alert #%d acknowledged by %s", alert.alert_number, data.user_id)
        return alert

    async def dismiss(self, alert_id: UUID, data: AlertDismiss) -> Alert:
        """
        Dismiss an alert without treating it as acknowledged action taken.

        Raises:
            AlertNotFoundError: If alert not found.
            InvalidAlertTransitionError: If alert is already in a terminal state.
        """
        alert = await self._repo.get_by_id(alert_id)
        if alert is None:
            raise AlertNotFoundError(alert_id)

        if not is_valid_alert_transition(alert.status, AlertStatus.DISMISSED):
            raise InvalidAlertTransitionError(alert.status, AlertStatus.DISMISSED)

        alert.status = AlertStatus.DISMISSED
        alert.dismissed_by = data.user_id
        alert.dismissed_at = datetime.now(timezone.utc)

        alert = await self._repo.update(alert)

        logger.info("Alert #%d dismissed by %s: %s", alert.alert_number, data.user_id, data.reason or "")
        return alert

    async def list_alerts(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Alert]:
        """List alerts with optional filtering and pagination."""
        return await self._repo.list_all(
            status=status, severity=severity, camera_id=camera_id, limit=limit, offset=offset,
        )

    async def count_alerts(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[str] = None,
    ) -> int:
        """Count alerts matching filters."""
        return await self._repo.count(status=status, severity=severity)

    async def get_notification_history(self, alert_id: UUID) -> List[NotificationLog]:
        """
        Get the full notification delivery history for an alert.

        Raises:
            AlertNotFoundError: If alert not found.
        """
        alert = await self._repo.get_by_id(alert_id)
        if alert is None:
            raise AlertNotFoundError(alert_id)
        return await self._repo.get_notification_logs(alert_id)

    async def process_pending_retries(self) -> List[NotificationLog]:
        """
        Process all notification retries that are currently due.

        Intended to be invoked periodically by a background scheduler.
        """
        return await self._dispatcher.process_retries()

    async def has_active_alert_for_incident(self, incident_id: UUID) -> bool:
        """Check whether an active (non-terminal) alert exists for an incident."""
        existing = await self._repo.get_active_by_incident(incident_id)
        return existing is not None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _meets_threshold(self, risk_level: str) -> bool:
        """Whether risk_level is at or above the configured minimum for alerting."""
        incoming = _SEVERITY_ORDER.get(risk_level, -1)
        minimum = _SEVERITY_ORDER.get(self._config.min_severity_for_alert, 1)
        return incoming >= minimum

    async def _is_duplicate(self, incident_id: UUID) -> bool:
        """
        Determine whether a new alert for this incident should be suppressed.

        Suppressed if:
        - An active (non-terminal) alert already exists for the incident, OR
        - Any alert for this incident was created within the dedupe window,
          even if that alert has since been acknowledged/dismissed.
        """
        active = await self._repo.get_active_by_incident(incident_id)
        if active is not None:
            return True

        if self._config.dedupe_window_seconds > 0:
            since = datetime.now(timezone.utc) - timedelta(seconds=self._config.dedupe_window_seconds)
            recent = await self._repo.get_recent_by_incident(incident_id, since)
            if recent:
                return True

        return False

    @staticmethod
    def _render_content(
        threat_type: str,
        risk_level: str,
        risk_score: float,
        camera_id: str,
        location_name: str,
    ) -> tuple:
        """Build the alert title and message from incident details."""
        location = f" at {location_name}" if location_name else ""
        title = f"{risk_level}: {threat_type.capitalize()} detected"
        message = (
            f"{threat_type.capitalize()} detected on camera '{camera_id}'{location}. "
            f"Risk score: {risk_score:.1f}/100 ({risk_level})."
        )
        return title, message
