"""
Alert & Notification Configuration

All notification channel settings — including any credentials — are loaded
exclusively from environment variables via Pydantic Settings. Nothing is
hard-coded. Every credential field defaults to an empty string and the
corresponding provider treats an empty credential as "not configured"
(it will log a warning and skip delivery rather than fail insecurely).
"""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AlertConfig(BaseSettings):
    """Configuration for alert creation and notification dispatch."""

    model_config = SettingsConfigDict(
        env_prefix="ALERT_",
        env_file=".env",
        extra="ignore",
    )

    # --- Alert creation thresholds ---
    min_severity_for_alert: str = Field(
        default="MEDIUM",
        description=(
            "Minimum incident risk level that generates an alert. "
            "Incidents scored LOW never generate alerts."
        ),
    )

    # --- Enabled channels ---
    enabled_channels: List[str] = Field(
        default=["console"],
        description=(
            "Notification channels to dispatch to, in order. "
            "Options: console, webhook, email. "
            "'console' is always safe to enable (local logging only)."
        ),
    )

    # --- Retry policy ---
    max_retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum delivery attempts per notification before giving up.",
    )
    retry_backoff_seconds: int = Field(
        default=30,
        ge=1,
        description="Base delay between retry attempts (exponential backoff multiplier).",
    )

    # --- Deduplication ---
    dedupe_window_seconds: int = Field(
        default=300,
        ge=0,
        description=(
            "Minimum seconds between alerts for the same incident/track before "
            "a new alert is suppressed as a duplicate. 0 disables the window "
            "(still blocks exact duplicate active alerts per incident)."
        ),
    )

    # --- Webhook channel credentials (empty = not configured) ---
    webhook_url: str = Field(
        default="",
        description="Webhook endpoint URL (Slack/Teams/PagerDuty/etc.). Empty disables the channel.",
    )
    webhook_auth_token: str = Field(
        default="",
        description="Bearer token for webhook authentication. Loaded from env only, never hard-coded.",
    )
    webhook_timeout_seconds: float = Field(
        default=5.0,
        ge=0.5,
        description="HTTP timeout for webhook delivery attempts.",
    )

    # --- Email channel credentials (empty = not configured) ---
    smtp_host: str = Field(default="", description="SMTP server hostname. Empty disables the channel.")
    smtp_port: int = Field(default=587, description="SMTP server port.")
    smtp_username: str = Field(default="", description="SMTP auth username. Loaded from env only.")
    smtp_password: str = Field(default="", description="SMTP auth password. Loaded from env only, never hard-coded.")
    smtp_from_address: str = Field(default="", description="From address for outgoing alert emails.")
    smtp_recipients: List[str] = Field(
        default=[],
        description="Recipient email addresses for alert notifications.",
    )
