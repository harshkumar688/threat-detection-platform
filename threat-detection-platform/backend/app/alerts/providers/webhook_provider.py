"""
Webhook Notification Provider

Delivers alerts to a generic HTTP webhook endpoint (Slack, Microsoft Teams,
PagerDuty, or any custom receiver that accepts a JSON POST). The endpoint
URL and bearer token are read exclusively from AlertConfig — populated
from environment variables. Nothing is hard-coded.
"""

import logging

from ..config import AlertConfig
from ..models import Alert, NotificationChannel
from .base import NotificationProvider, NotificationResult

logger = logging.getLogger("app.alerts.notifications.webhook")


class WebhookNotificationProvider(NotificationProvider):
    """Delivers alerts via HTTP POST to a configured webhook URL."""

    def __init__(self, config: AlertConfig):
        self._config = config

    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.WEBHOOK

    @property
    def is_configured(self) -> bool:
        return bool(self._config.webhook_url)

    async def send(self, alert: Alert) -> NotificationResult:
        if not self.is_configured:
            return NotificationResult(
                success=False,
                error_message="Webhook channel not configured (ALERT_WEBHOOK_URL is empty)",
            )

        payload = {
            "alert_id": str(alert.id),
            "alert_number": alert.alert_number,
            "incident_id": str(alert.incident_id),
            "camera_id": alert.camera_id,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "created_at": alert.created_at.isoformat(),
        }

        headers = {}
        if self._config.webhook_auth_token:
            headers["Authorization"] = f"Bearer {self._config.webhook_auth_token}"

        try:
            import httpx

            async with httpx.AsyncClient(timeout=self._config.webhook_timeout_seconds) as client:
                response = await client.post(self._config.webhook_url, json=payload, headers=headers)

            if 200 <= response.status_code < 300:
                return NotificationResult(success=True)

            return NotificationResult(
                success=False,
                error_message=f"Webhook returned HTTP {response.status_code}",
            )

        except ImportError:
            return NotificationResult(success=False, error_message="httpx not installed")
        except Exception as e:
            # Never leak secrets in the error message
            logger.warning("Webhook delivery failed: %s", type(e).__name__)
            return NotificationResult(success=False, error_message=f"Delivery error: {type(e).__name__}")
