"""
Email Notification Provider

Delivers alerts via SMTP. All connection details (host, port, username,
password, sender, recipients) are read exclusively from AlertConfig —
populated from environment variables. Nothing is hard-coded, and the
password is never logged.
"""

import logging
from email.message import EmailMessage

from ..config import AlertConfig
from ..models import Alert, NotificationChannel
from .base import NotificationProvider, NotificationResult

logger = logging.getLogger("app.alerts.notifications.email")


class EmailNotificationProvider(NotificationProvider):
    """Delivers alerts via SMTP email."""

    def __init__(self, config: AlertConfig):
        self._config = config

    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.EMAIL

    @property
    def is_configured(self) -> bool:
        return bool(
            self._config.smtp_host
            and self._config.smtp_from_address
            and self._config.smtp_recipients
        )

    async def send(self, alert: Alert) -> NotificationResult:
        if not self.is_configured:
            return NotificationResult(
                success=False,
                error_message="Email channel not configured (SMTP host/from/recipients missing)",
            )

        msg = EmailMessage()
        msg["Subject"] = f"[{alert.severity.value}] {alert.title}"
        msg["From"] = self._config.smtp_from_address
        msg["To"] = ", ".join(self._config.smtp_recipients)
        msg.set_content(
            f"{alert.message}\n\n"
            f"Incident: {alert.incident_id}\n"
            f"Camera: {alert.camera_id}\n"
            f"Severity: {alert.severity.value}\n"
            f"Created: {alert.created_at.isoformat()}\n"
        )

        try:
            import asyncio
            import smtplib

            def _send_sync():
                with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port, timeout=10) as server:
                    server.starttls()
                    if self._config.smtp_username:
                        server.login(self._config.smtp_username, self._config.smtp_password)
                    server.send_message(msg)

            await asyncio.to_thread(_send_sync)
            return NotificationResult(success=True)

        except Exception as e:
            # Never leak SMTP credentials in error output
            logger.warning("Email delivery failed: %s", type(e).__name__)
            return NotificationResult(success=False, error_message=f"Delivery error: {type(e).__name__}")
