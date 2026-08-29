"""
Console Notification Provider

Logs the alert to the application logger. Always "configured" — useful
as a zero-dependency default channel and in development/testing where no
external notification service is available.
"""

import logging

from ..models import Alert, NotificationChannel
from .base import NotificationProvider, NotificationResult

logger = logging.getLogger("app.alerts.notifications.console")


class ConsoleNotificationProvider(NotificationProvider):
    """Logs alerts to the application log. No external dependency, no credentials."""

    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.CONSOLE

    @property
    def is_configured(self) -> bool:
        return True

    async def send(self, alert: Alert) -> NotificationResult:
        logger.warning(
            "ALERT [%s] #%d %s — %s (incident=%s, camera=%s)",
            alert.severity.value,
            alert.alert_number,
            alert.title,
            alert.message,
            alert.incident_id,
            alert.camera_id,
        )
        return NotificationResult(success=True)
