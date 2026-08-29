"""
Notification Provider Interface

Abstract base that ALL notification channels must implement. This is the
isolation boundary requested: business logic (AlertService, dispatcher)
never imports a concrete provider directly — only this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from ..models import Alert, NotificationChannel


@dataclass
class NotificationResult:
    """Outcome of a single delivery attempt."""

    success: bool
    error_message: Optional[str] = None


class NotificationProvider(ABC):
    """
    Abstract notification channel.

    Concrete implementations (console, webhook, email, SMS, ...) must:
    - Never raise on delivery failure — return a NotificationResult instead.
      Raising is reserved for programmer errors, not transient network issues.
    - Treat missing/empty credentials as "not configured": return a failed
      NotificationResult with a clear message rather than crashing.
    - Never log secret values (tokens, passwords).
    """

    @property
    @abstractmethod
    def channel(self) -> NotificationChannel:
        """The channel identifier this provider implements."""
        ...

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this provider has the minimum configuration to attempt delivery."""
        ...

    @abstractmethod
    async def send(self, alert: Alert) -> NotificationResult:
        """
        Attempt to deliver a notification for the given alert.

        Must not raise for expected failure modes (network errors, timeouts,
        missing configuration). Must return a NotificationResult describing
        the outcome so the dispatcher can log and decide on retries.
        """
        ...
