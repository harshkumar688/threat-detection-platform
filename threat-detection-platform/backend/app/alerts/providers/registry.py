"""
Provider Registry

Single place that knows how to map a channel name (from AlertConfig)
to a concrete NotificationProvider instance. AlertService and the
dispatcher never construct providers themselves — they call
`build_providers_from_config()` and work only with the abstract
`NotificationProvider` interface afterward.
"""

import logging
from typing import List

from ..config import AlertConfig
from .base import NotificationProvider
from .console_provider import ConsoleNotificationProvider
from .email_provider import EmailNotificationProvider
from .webhook_provider import WebhookNotificationProvider

logger = logging.getLogger("app.alerts.providers.registry")


def build_providers_from_config(config: AlertConfig) -> List[NotificationProvider]:
    """
    Construct the list of enabled notification providers from configuration.

    Channels not present in `config.enabled_channels` are skipped entirely.
    Channels present but missing required credentials are still constructed
    (so they appear in logs/status) but will report `is_configured == False`
    and fail gracefully on send() rather than being silently dropped.
    """
    providers: List[NotificationProvider] = []

    for channel_name in config.enabled_channels:
        if channel_name == "console":
            providers.append(ConsoleNotificationProvider())
        elif channel_name == "webhook":
            providers.append(WebhookNotificationProvider(config))
        elif channel_name == "email":
            providers.append(EmailNotificationProvider(config))
        else:
            logger.warning("Unknown notification channel in config, skipping: %s", channel_name)

    for p in providers:
        if not p.is_configured:
            logger.info(
                "Notification channel '%s' is enabled but not fully configured; "
                "deliveries on this channel will fail until credentials are set.",
                p.channel.value,
            )

    return providers
