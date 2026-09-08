"""
Alert Repository (Data Access Layer)

Abstract interface for alert + notification log persistence, plus an
in-memory implementation for testing and development without a database.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from .models import Alert, AlertStatus, NotificationLog


class AlertRepository(ABC):
    """Abstract repository interface for alerts and notification logs."""

    @abstractmethod
    async def create(self, alert: Alert) -> Alert:
        """Persist a new alert. Returns the alert with assigned number."""
        ...

    @abstractmethod
    async def get_by_id(self, alert_id: UUID) -> Optional[Alert]:
        """Retrieve an alert by ID. Returns None if not found."""
        ...

    @abstractmethod
    async def update(self, alert: Alert) -> Alert:
        """Persist updated alert state."""
        ...

    @abstractmethod
    async def list_all(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Alert]:
        """List alerts with optional filters and pagination."""
        ...

    @abstractmethod
    async def count(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[str] = None,
    ) -> int:
        """Count alerts matching filters."""
        ...

    @abstractmethod
    async def get_active_by_incident(self, incident_id: UUID) -> Optional[Alert]:
        """Find a non-terminal (not acknowledged/dismissed) alert for an incident."""
        ...

    @abstractmethod
    async def get_recent_by_incident(self, incident_id: UUID, since: datetime) -> List[Alert]:
        """Get alerts for an incident created at or after `since` (for dedupe windows)."""
        ...

    @abstractmethod
    async def add_notification_log(self, log: NotificationLog) -> NotificationLog:
        """Persist a notification delivery attempt log entry."""
        ...

    @abstractmethod
    async def update_notification_log(self, log: NotificationLog) -> NotificationLog:
        """Persist an updated notification log entry (e.g., after a retry)."""
        ...

    @abstractmethod
    async def get_notification_logs(self, alert_id: UUID) -> List[NotificationLog]:
        """Get all notification log entries for an alert, ordered by creation time."""
        ...

    @abstractmethod
    async def get_pending_retries(self, before: datetime) -> List[NotificationLog]:
        """Get notification logs eligible for retry (FAILED, retry due, attempts remaining)."""
        ...


class InMemoryAlertRepository(AlertRepository):
    """In-memory implementation for testing and development. Not for production."""

    def __init__(self):
        self._alerts: Dict[UUID, Alert] = {}
        self._notification_logs: Dict[UUID, NotificationLog] = {}
        self._next_number: int = 1

    async def create(self, alert: Alert) -> Alert:
        alert.alert_number = self._next_number
        self._next_number += 1
        self._alerts[alert.id] = alert
        return alert

    async def get_by_id(self, alert_id: UUID) -> Optional[Alert]:
        return self._alerts.get(alert_id)

    async def update(self, alert: Alert) -> Alert:
        alert.updated_at = datetime.now(timezone.utc)
        self._alerts[alert.id] = alert
        return alert

    async def list_all(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Alert]:
        results = list(self._alerts.values())

        if status:
            results = [a for a in results if a.status == status]
        if severity:
            results = [a for a in results if a.severity.value == severity]
        if camera_id:
            results = [a for a in results if a.camera_id == camera_id]

        results.sort(key=lambda a: a.created_at, reverse=True)
        return results[offset:offset + limit]

    async def count(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[str] = None,
    ) -> int:
        results = list(self._alerts.values())
        if status:
            results = [a for a in results if a.status == status]
        if severity:
            results = [a for a in results if a.severity.value == severity]
        return len(results)

    async def get_active_by_incident(self, incident_id: UUID) -> Optional[Alert]:
        terminal = {AlertStatus.ACKNOWLEDGED, AlertStatus.DISMISSED}
        for alert in self._alerts.values():
            if alert.incident_id == incident_id and alert.status not in terminal:
                return alert
        return None

    async def get_recent_by_incident(self, incident_id: UUID, since: datetime) -> List[Alert]:
        return [
            a for a in self._alerts.values()
            if a.incident_id == incident_id and a.created_at >= since
        ]

    async def add_notification_log(self, log: NotificationLog) -> NotificationLog:
        self._notification_logs[log.id] = log
        return log

    async def update_notification_log(self, log: NotificationLog) -> NotificationLog:
        self._notification_logs[log.id] = log
        return log

    async def get_notification_logs(self, alert_id: UUID) -> List[NotificationLog]:
        logs = [l for l in self._notification_logs.values() if l.alert_id == alert_id]
        logs.sort(key=lambda l: l.created_at)
        return logs

    async def get_pending_retries(self, before: datetime) -> List[NotificationLog]:
        from .models import NotificationStatus

        return [
            l for l in self._notification_logs.values()
            if l.status == NotificationStatus.FAILED
            and l.next_retry_at is not None
            and l.next_retry_at <= before
            and l.attempt_number < l.max_attempts
        ]

    def clear(self):
        """Clear all data (for testing)."""
        self._alerts.clear()
        self._notification_logs.clear()
        self._next_number = 1


class SqlAlertRepository(AlertRepository):
    """Durable alert repository backed by the generic document store."""

    def __init__(self):
        from app.db import DocumentStore
        self._alerts_store = DocumentStore("alert")
        self._notif_store = DocumentStore("notification_log")

    async def create(self, alert: Alert) -> Alert:
        seq = await self._alerts_store.upsert(str(alert.id), alert.model_dump(mode="json"), seq=None)
        alert.alert_number = seq
        await self._alerts_store.upsert(str(alert.id), alert.model_dump(mode="json"), seq=seq)
        return alert

    async def get_by_id(self, alert_id: UUID) -> Optional[Alert]:
        data = await self._alerts_store.get(str(alert_id))
        return Alert(**{k: v for k, v in data.items() if k != "_seq"}) if data else None

    async def update(self, alert: Alert) -> Alert:
        alert.updated_at = datetime.now(timezone.utc)
        await self._alerts_store.upsert(str(alert.id), alert.model_dump(mode="json"), seq=alert.alert_number)
        return alert

    async def list_all(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Alert]:
        results = [
            Alert(**{k: v for k, v in d.items() if k != "_seq"})
            for d in await self._alerts_store.list_all()
        ]
        if status:
            results = [a for a in results if a.status == status]
        if severity:
            results = [a for a in results if a.severity.value == severity]
        if camera_id:
            results = [a for a in results if a.camera_id == camera_id]
        results.sort(key=lambda a: a.created_at, reverse=True)
        return results[offset:offset + limit]

    async def count(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[str] = None,
    ) -> int:
        results = [
            Alert(**{k: v for k, v in d.items() if k != "_seq"})
            for d in await self._alerts_store.list_all()
        ]
        if status:
            results = [a for a in results if a.status == status]
        if severity:
            results = [a for a in results if a.severity.value == severity]
        return len(results)

    async def get_active_by_incident(self, incident_id: UUID) -> Optional[Alert]:
        terminal = {AlertStatus.ACKNOWLEDGED, AlertStatus.DISMISSED}
        for data in await self._alerts_store.list_all():
            alert = Alert(**{k: v for k, v in data.items() if k != "_seq"})
            if alert.incident_id == incident_id and alert.status not in terminal:
                return alert
        return None

    async def get_recent_by_incident(self, incident_id: UUID, since: datetime) -> List[Alert]:
        results = [
            Alert(**{k: v for k, v in d.items() if k != "_seq"})
            for d in await self._alerts_store.list_all()
        ]
        return [a for a in results if a.incident_id == incident_id and a.created_at >= since]

    async def add_notification_log(self, log: NotificationLog) -> NotificationLog:
        await self._notif_store.upsert(str(log.id), log.model_dump(mode="json"))
        return log

    async def update_notification_log(self, log: NotificationLog) -> NotificationLog:
        await self._notif_store.upsert(str(log.id), log.model_dump(mode="json"))
        return log

    async def get_notification_logs(self, alert_id: UUID) -> List[NotificationLog]:
        logs = [
            NotificationLog(**{k: v for k, v in d.items() if k != "_seq"})
            for d in await self._notif_store.list_all()
        ]
        logs = [l for l in logs if l.alert_id == alert_id]
        logs.sort(key=lambda l: l.created_at)
        return logs

    async def get_pending_retries(self, before: datetime) -> List[NotificationLog]:
        from .models import NotificationStatus
        logs = [
            NotificationLog(**{k: v for k, v in d.items() if k != "_seq"})
            for d in await self._notif_store.list_all()
        ]
        return [
            l for l in logs
            if l.status == NotificationStatus.FAILED
            and l.next_retry_at is not None
            and l.next_retry_at <= before
            and l.attempt_number < l.max_attempts
        ]

    def clear(self):
        """Sync clear — for test compatibility; async version also available."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._alerts_store.clear())
                asyncio.create_task(self._notif_store.clear())
            else:
                loop.run_until_complete(self._alerts_store.clear())
                loop.run_until_complete(self._notif_store.clear())
        except Exception:
            pass
