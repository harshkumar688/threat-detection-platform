"""
Alert Management Module

Creates and manages alerts raised from confirmed incidents, dispatches
notifications through configurable, pluggable channels, and tracks the
full delivery + acknowledgement lifecycle.

Architecture:
    ┌────────────────────┐
    │  API Router        │  ← HTTP endpoints (app/api/v1/alerts.py)
    └─────────┬──────────┘
              │
    ┌─────────▼──────────┐
    │  AlertService       │  ← Business logic: create, dedupe, dispatch, ack
    └─────┬──────────┬────┘
          │          │
    ┌─────▼───┐  ┌────▼──────────────────┐
    │ AlertRepo│  │ NotificationDispatcher │
    └──────────┘  └────────────┬───────────┘
                                │
                  ┌─────────────▼─────────────┐
                  │  NotificationProvider      │  ← Abstract interface
                  │  (Console / Webhook /      │
                  │   Email, ...)              │
                  └────────────────────────────┘

Notification providers are never referenced directly by business logic —
only through the `NotificationProvider` interface, so new channels (SMS,
Slack, PagerDuty, etc.) can be added without touching AlertService.

No credentials are hard-coded anywhere in this module. All channel
credentials (webhook tokens, SMTP passwords) are loaded from environment
variables via AlertConfig and default to empty strings.
"""

from .config import AlertConfig
from .dispatcher import NotificationDispatcher
from .exceptions import (
    AlertError,
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
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
    is_valid_alert_transition,
)
from .repository import AlertRepository, InMemoryAlertRepository, SqlAlertRepository
from .service import AlertService, risk_level_to_alert_severity

__all__ = [
    "AlertConfig",
    "NotificationDispatcher",
    "AlertError",
    "AlertNotFoundError",
    "BelowAlertThresholdError",
    "DuplicateAlertError",
    "InvalidAlertTransitionError",
    "Alert",
    "AlertAcknowledge",
    "AlertCreate",
    "AlertDismiss",
    "AlertSeverity",
    "AlertStatus",
    "NotificationChannel",
    "NotificationLog",
    "NotificationStatus",
    "is_valid_alert_transition",
    "AlertRepository",
    "InMemoryAlertRepository",
    "SqlAlertRepository",
    "AlertService",
    "risk_level_to_alert_severity",
]
