"""
Notification Dispatcher

Sends a given alert through every configured NotificationProvider,
records a NotificationLog entry for each attempt (success or failure),
and schedules retries with exponential backoff for failed deliveries.

This is the only piece of business logic that touches concrete
providers — and even here, only through the abstract
`NotificationProvider` interface, never a specific implementation.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from .config import AlertConfig
from .models import Alert, NotificationLog, NotificationStatus
from .providers.base import NotificationProvider
from .repository import AlertRepository

logger = logging.getLogger("app.alerts.dispatcher")


class NotificationDispatcher:
    """
    Dispatches alert notifications across all configured providers.

    Usage:
        dispatcher = NotificationDispatcher(config, providers, repo)
        logs = await dispatcher.dispatch(alert)

        # Periodically (e.g., background task):
        await dispatcher.process_retries()
    """

    def __init__(
        self,
        config: AlertConfig,
        providers: List[NotificationProvider],
        repository: AlertRepository,
    ):
        self._config = config
        self._providers = providers
        self._repo = repository

    async def dispatch(self, alert: Alert) -> List[NotificationLog]:
        """
        Send the alert through every configured provider.

        Each provider gets its own NotificationLog entry regardless of
        outcome. Failures schedule a retry (if attempts remain) rather
        than raising — dispatch() never fails the calling incident/alert
        creation flow.
        """
        logs: List[NotificationLog] = []

        for provider in self._providers:
            log = NotificationLog(
                alert_id=alert.id,
                channel=provider.channel,
                attempt_number=1,
                max_attempts=self._config.max_retry_attempts,
            )
            log = await self._attempt_delivery(provider, alert, log, is_new=True)
            logs.append(log)

        return logs

    async def process_retries(self) -> List[NotificationLog]:
        """
        Attempt redelivery for all notification logs whose retry is due.

        Intended to be called periodically by a background task/scheduler.
        Returns the updated logs (successful or newly-failed-again).
        """
        now = datetime.now(timezone.utc)
        due = await self._repo.get_pending_retries(before=now)
        results: List[NotificationLog] = []

        for log in due:
            provider = next((p for p in self._providers if p.channel == log.channel), None)
            if provider is None:
                continue

            # We need the alert to re-render the notification payload
            alert = await self._get_alert_for_log(log)
            if alert is None:
                continue

            log.attempt_number += 1
            log.status = NotificationStatus.RETRYING
            log = await self._attempt_delivery(provider, alert, log, is_new=False)
            results.append(log)

        return results

    async def _attempt_delivery(
        self,
        provider: NotificationProvider,
        alert: Alert,
        log: NotificationLog,
        is_new: bool,
    ) -> NotificationLog:
        """Perform a single delivery attempt and update the log accordingly."""
        result = await provider.send(alert)

        if result.success:
            log.status = NotificationStatus.SENT
            log.sent_at = datetime.now(timezone.utc)
            log.error_message = None
            log.next_retry_at = None
            logger.info(
                "Notification delivered: alert=%s channel=%s attempt=%d",
                alert.id, provider.channel.value, log.attempt_number,
            )
        else:
            log.status = NotificationStatus.FAILED
            log.error_message = result.error_message

            if log.can_retry:
                backoff = self._config.retry_backoff_seconds * (2 ** (log.attempt_number - 1))
                log.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
                logger.warning(
                    "Notification delivery failed, will retry: alert=%s channel=%s "
                    "attempt=%d/%d next_retry_in=%ds reason=%s",
                    alert.id, provider.channel.value, log.attempt_number,
                    log.max_attempts, backoff, result.error_message,
                )
            else:
                log.next_retry_at = None
                logger.error(
                    "Notification delivery failed permanently: alert=%s channel=%s "
                    "attempts=%d reason=%s",
                    alert.id, provider.channel.value, log.attempt_number, result.error_message,
                )

        if is_new:
            log = await self._repo.add_notification_log(log)
        else:
            log = await self._repo.update_notification_log(log)

        return log

    async def _get_alert_for_log(self, log: NotificationLog):
        """Look up the parent alert for a notification log entry (for retries)."""
        # AlertRepository doesn't expose alert lookup by notification log directly;
        # this is a thin helper so retries can re-render the payload.
        from uuid import UUID

        get_by_id = getattr(self._repo, "get_by_id", None)
        if get_by_id is None:
            return None
        return await get_by_id(log.alert_id)
