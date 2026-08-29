"""
Notification Providers

Every concrete channel (console, webhook, email, ...) implements the
`NotificationProvider` interface. AlertService and NotificationDispatcher
depend only on this abstract interface — never on a concrete provider —
so new channels can be added without touching business logic.
"""

from .base import NotificationProvider, NotificationResult
from .console_provider import ConsoleNotificationProvider
from .webhook_provider import WebhookNotificationProvider
from .email_provider import EmailNotificationProvider
from .registry import build_providers_from_config

__all__ = [
    "NotificationProvider",
    "NotificationResult",
    "ConsoleNotificationProvider",
    "WebhookNotificationProvider",
    "EmailNotificationProvider",
    "build_providers_from_config",
]
