"""
Alert Schemas
"""

from typing import Optional

from pydantic import BaseModel, Field


class AlertResponse(BaseModel):
    """Alert detail response."""

    id: str
    alert_number: int = 0
    incident_id: str
    camera_id: str
    severity: str
    title: str
    message: str
    status: str = "PENDING"
    is_acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: str | None = None
    acknowledgement_notes: str | None = None
    dismissed_by: str | None = None
    dismissed_at: str | None = None
    created_at: str
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class NotificationLogResponse(BaseModel):
    """A single notification delivery attempt record."""

    id: str
    channel: str
    status: str
    attempt_number: int
    max_attempts: int
    error_message: str | None = None
    created_at: str
    sent_at: str | None = None
    next_retry_at: str | None = None


class AlertAcknowledgeRequest(BaseModel):
    """Acknowledge an alert."""

    notes: Optional[str] = Field(default=None, max_length=500)


class AlertDismissRequest(BaseModel):
    """Dismiss an alert without treating it as an acknowledged threat."""

    reason: Optional[str] = Field(default=None, max_length=500)


class AlertCountResponse(BaseModel):
    """Alert counts for dashboard badge."""

    total_unread: int
    total_unacknowledged: int
    by_severity: dict = {}
