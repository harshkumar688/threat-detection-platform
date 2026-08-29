"""
Alert Domain Models

Defines alert severity/status, notification channel/status enums, and
the core Alert / NotificationLog entities plus their creation DTOs.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    """
    Alert severity levels.

    Deliberately excludes LOW — alerts exist to demand attention. Incidents
    scored as LOW risk should not generate an alert at all (see AlertService).
    """

    MEDIUM = "MEDIUM"
    """Worth reviewing soon; not immediately dangerous."""

    HIGH = "HIGH"
    """Likely real threat; prioritize response."""

    CRITICAL = "CRITICAL"
    """Maximum urgency; immediate response required."""


class AlertStatus(str, Enum):
    """Alert lifecycle states."""

    PENDING = "PENDING"
    """Created, notifications not yet dispatched."""

    DISPATCHED = "DISPATCHED"
    """At least one notification channel attempted delivery."""

    ACKNOWLEDGED = "ACKNOWLEDGED"
    """An operator has acknowledged the alert."""

    DISMISSED = "DISMISSED"
    """Alert dismissed without action (e.g., known false alarm)."""


# Valid state transitions for alerts
VALID_ALERT_TRANSITIONS: Dict[AlertStatus, List[AlertStatus]] = {
    AlertStatus.PENDING: [AlertStatus.DISPATCHED, AlertStatus.ACKNOWLEDGED, AlertStatus.DISMISSED],
    AlertStatus.DISPATCHED: [AlertStatus.ACKNOWLEDGED, AlertStatus.DISMISSED],
    AlertStatus.ACKNOWLEDGED: [],  # Terminal
    AlertStatus.DISMISSED: [],     # Terminal
}


def is_valid_alert_transition(from_status: AlertStatus, to_status: AlertStatus) -> bool:
    """Check if an alert status transition is allowed."""
    return to_status in VALID_ALERT_TRANSITIONS.get(from_status, [])


class NotificationChannel(str, Enum):
    """Supported notification delivery channels."""

    CONSOLE = "console"     # Local/dev logging channel — always available
    WEBHOOK = "webhook"      # Generic HTTP webhook (Slack/Teams/PagerDuty/etc.)
    EMAIL = "email"          # SMTP email


class NotificationStatus(str, Enum):
    """Delivery status of a single notification attempt."""

    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class Alert(BaseModel):
    """
    Core alert entity.

    Created from a confirmed incident. One incident maps to at most one
    active (non-dismissed/non-acknowledged... actually exactly one, period —
    see AlertService duplicate-prevention) alert.
    """

    id: UUID = Field(default_factory=uuid4)
    alert_number: int = Field(default=0, description="Sequential human-readable number")

    incident_id: UUID = Field(description="Source incident that triggered this alert")
    camera_id: str = Field(description="Source camera identifier")

    severity: AlertSeverity = Field(description="Alert severity level")
    title: str = Field(description="Short human-readable title")
    message: str = Field(description="Full alert message/description")

    status: AlertStatus = Field(default=AlertStatus.PENDING)

    # Acknowledgement
    is_acknowledged: bool = Field(default=False)
    acknowledged_by: Optional[str] = Field(default=None)
    acknowledged_at: Optional[datetime] = Field(default=None)
    acknowledgement_notes: Optional[str] = Field(default=None)

    # Dismissal
    dismissed_by: Optional[str] = Field(default=None)
    dismissed_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class AlertCreate(BaseModel):
    """DTO for creating a new alert from a confirmed incident."""

    incident_id: UUID
    camera_id: str
    severity: AlertSeverity
    title: str
    message: str


class AlertAcknowledge(BaseModel):
    """DTO for acknowledging an alert."""

    user_id: str
    notes: Optional[str] = None


class AlertDismiss(BaseModel):
    """DTO for dismissing an alert."""

    user_id: str
    reason: Optional[str] = None


class NotificationLog(BaseModel):
    """
    Record of a single notification delivery attempt.

    One alert can have multiple NotificationLog entries — one per
    configured channel, plus additional entries for retries.
    """

    id: UUID = Field(default_factory=uuid4)
    alert_id: UUID
    channel: NotificationChannel
    status: NotificationStatus = Field(default=NotificationStatus.PENDING)

    attempt_number: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=3, ge=1)

    error_message: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = Field(default=None)
    next_retry_at: Optional[datetime] = Field(default=None)

    model_config = {"from_attributes": True}

    @property
    def can_retry(self) -> bool:
        """Whether another retry attempt is permitted."""
        return self.status == NotificationStatus.FAILED and self.attempt_number < self.max_attempts


# Backward/forward-compatible alias used in a couple of call sites & tests
NotificationDeliveryStatus = NotificationStatus
