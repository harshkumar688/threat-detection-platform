"""
Alert Service Unit Tests

Tests:
- Alert creation from confirmed incidents
- Severity threshold enforcement (LOW never alerts)
- Duplicate-alert prevention (active alert + dedupe window)
- State machine transitions (acknowledge/dismiss)
- Notification dispatch across providers
- Retry scheduling and processing
- Notification logging (every attempt recorded)
- No hard-coded credentials — providers report unconfigured cleanly
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.alerts import (
    AlertAcknowledge,
    AlertConfig,
    AlertDismiss,
    AlertService,
    AlertStatus,
    InMemoryAlertRepository,
    NotificationDispatcher,
    NotificationStatus,
    is_valid_alert_transition,
)
from app.alerts.exceptions import (
    AlertNotFoundError,
    BelowAlertThresholdError,
    DuplicateAlertError,
    InvalidAlertTransitionError,
)
from app.alerts.providers.base import NotificationProvider, NotificationResult
from app.alerts.models import AlertSeverity, NotificationChannel


# =============================================================================
# Test doubles
# =============================================================================

class FakeProvider(NotificationProvider):
    """Configurable in-memory provider for testing dispatch/retry behavior."""

    def __init__(self, channel: NotificationChannel, configured: bool = True, fail_times: int = 0):
        self._channel = channel
        self._configured = configured
        self._fail_times = fail_times
        self.send_calls = 0

    @property
    def channel(self) -> NotificationChannel:
        return self._channel

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def send(self, alert) -> NotificationResult:
        self.send_calls += 1
        if not self._configured:
            return NotificationResult(success=False, error_message="not configured")
        if self.send_calls <= self._fail_times:
            return NotificationResult(success=False, error_message="simulated failure")
        return NotificationResult(success=True)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def repo():
    return InMemoryAlertRepository()


@pytest.fixture
def config():
    return AlertConfig(
        min_severity_for_alert="MEDIUM",
        enabled_channels=["console"],
        max_retry_attempts=3,
        retry_backoff_seconds=1,
        dedupe_window_seconds=300,
    )


def make_service(config, repo, providers=None):
    providers = providers if providers is not None else [FakeProvider(NotificationChannel.CONSOLE)]
    dispatcher = NotificationDispatcher(config, providers, repo)
    return AlertService(config, repo, dispatcher), dispatcher


# =============================================================================
# Creation & Severity Threshold
# =============================================================================

class TestAlertCreation:
    @pytest.mark.asyncio
    async def test_create_from_high_risk_incident(self, config, repo):
        service, _ = make_service(config, repo)
        incident_id = uuid4()

        alert = await service.create_from_incident(
            incident_id=incident_id,
            camera_id="cam-01",
            risk_level="HIGH",
            threat_type="handgun",
            risk_score=75.0,
            location_name="Lobby",
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH
        assert alert.incident_id == incident_id
        assert alert.camera_id == "cam-01"
        assert "handgun" in alert.message.lower()
        assert alert.alert_number == 1

    @pytest.mark.asyncio
    async def test_critical_incident_creates_critical_alert(self, config, repo):
        service, _ = make_service(config, repo)
        alert = await service.create_from_incident(
            incident_id=uuid4(), camera_id="cam-02", risk_level="CRITICAL",
            threat_type="rifle", risk_score=95.0,
        )
        assert alert.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_low_risk_incident_produces_no_alert(self, config, repo):
        service, _ = make_service(config, repo)
        alert = await service.create_from_incident(
            incident_id=uuid4(), camera_id="cam-03", risk_level="LOW",
            threat_type="knife", risk_score=15.0,
        )
        assert alert is None

    @pytest.mark.asyncio
    async def test_medium_meets_default_threshold(self, config, repo):
        service, _ = make_service(config, repo)
        alert = await service.create_from_incident(
            incident_id=uuid4(), camera_id="cam-04", risk_level="MEDIUM",
            threat_type="knife", risk_score=40.0,
        )
        assert alert is not None
        assert alert.severity == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_custom_threshold_suppresses_medium(self, repo):
        strict_config = AlertConfig(min_severity_for_alert="HIGH", enabled_channels=["console"])
        service, _ = make_service(strict_config, repo)

        alert = await service.create_from_incident(
            incident_id=uuid4(), camera_id="cam-05", risk_level="MEDIUM",
            threat_type="knife", risk_score=40.0,
        )
        assert alert is None

    @pytest.mark.asyncio
    async def test_strict_variant_raises_below_threshold(self, config, repo):
        service, _ = make_service(config, repo)
        with pytest.raises(BelowAlertThresholdError):
            await service.create_from_incident_strict(
                incident_id=uuid4(), camera_id="cam-06", risk_level="LOW",
                threat_type="knife", risk_score=10.0,
            )

    @pytest.mark.asyncio
    async def test_sequential_alert_numbering(self, config, repo):
        service, _ = make_service(config, repo)
        a1 = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        a2 = await service.create_from_incident(uuid4(), "cam-02", "HIGH", "rifle", 80.0)
        assert a1.alert_number == 1
        assert a2.alert_number == 2


# =============================================================================
# Duplicate Prevention
# =============================================================================

class TestDuplicatePrevention:
    @pytest.mark.asyncio
    async def test_second_alert_for_same_active_incident_suppressed(self, config, repo):
        service, _ = make_service(config, repo)
        incident_id = uuid4()

        first = await service.create_from_incident(incident_id, "cam-01", "HIGH", "handgun", 70.0)
        second = await service.create_from_incident(incident_id, "cam-01", "HIGH", "handgun", 72.0)

        assert first is not None
        assert second is None

    @pytest.mark.asyncio
    async def test_strict_variant_raises_duplicate(self, config, repo):
        service, _ = make_service(config, repo)
        incident_id = uuid4()
        await service.create_from_incident(incident_id, "cam-01", "HIGH", "handgun", 70.0)

        with pytest.raises(DuplicateAlertError):
            await service.create_from_incident_strict(incident_id, "cam-01", "HIGH", "handgun", 70.0)

    @pytest.mark.asyncio
    async def test_dedupe_window_blocks_after_acknowledgement(self, config, repo):
        """Even after the first alert is acknowledged, a fresh alert within
        the dedupe window for the SAME incident should be suppressed."""
        service, _ = make_service(config, repo)
        incident_id = uuid4()

        alert = await service.create_from_incident(incident_id, "cam-01", "HIGH", "handgun", 70.0)
        await service.acknowledge(alert.id, AlertAcknowledge(user_id="op1"))

        second = await service.create_from_incident(incident_id, "cam-01", "HIGH", "handgun", 71.0)
        assert second is None

    @pytest.mark.asyncio
    async def test_zero_dedupe_window_still_blocks_active_alert(self, repo):
        """dedupe_window_seconds=0 disables the *time* window, but an
        active (non-terminal) alert for the same incident must still block."""
        cfg = AlertConfig(min_severity_for_alert="MEDIUM", enabled_channels=["console"], dedupe_window_seconds=0)
        service, _ = make_service(cfg, repo)
        incident_id = uuid4()

        first = await service.create_from_incident(incident_id, "cam-01", "HIGH", "handgun", 70.0)
        second = await service.create_from_incident(incident_id, "cam-01", "HIGH", "handgun", 70.0)

        assert first is not None
        assert second is None

    @pytest.mark.asyncio
    async def test_different_incidents_both_alert(self, config, repo):
        service, _ = make_service(config, repo)
        a1 = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        a2 = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        assert a1 is not None
        assert a2 is not None
        assert a1.id != a2.id

    @pytest.mark.asyncio
    async def test_has_active_alert_for_incident(self, config, repo):
        service, _ = make_service(config, repo)
        incident_id = uuid4()
        assert await service.has_active_alert_for_incident(incident_id) is False

        await service.create_from_incident(incident_id, "cam-01", "HIGH", "handgun", 70.0)
        assert await service.has_active_alert_for_incident(incident_id) is True


# =============================================================================
# Alert State Machine
# =============================================================================

class TestStateMachine:
    def test_valid_transitions(self):
        assert is_valid_alert_transition(AlertStatus.PENDING, AlertStatus.DISPATCHED) is True
        assert is_valid_alert_transition(AlertStatus.PENDING, AlertStatus.ACKNOWLEDGED) is True
        assert is_valid_alert_transition(AlertStatus.DISPATCHED, AlertStatus.ACKNOWLEDGED) is True
        assert is_valid_alert_transition(AlertStatus.DISPATCHED, AlertStatus.DISMISSED) is True

    def test_terminal_states_have_no_transitions(self):
        assert is_valid_alert_transition(AlertStatus.ACKNOWLEDGED, AlertStatus.DISMISSED) is False
        assert is_valid_alert_transition(AlertStatus.DISMISSED, AlertStatus.ACKNOWLEDGED) is False

    @pytest.mark.asyncio
    async def test_acknowledge_sets_fields(self, config, repo):
        service, _ = make_service(config, repo)
        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)

        updated = await service.acknowledge(alert.id, AlertAcknowledge(user_id="op1", notes="Verified real threat"))

        assert updated.status == AlertStatus.ACKNOWLEDGED
        assert updated.is_acknowledged is True
        assert updated.acknowledged_by == "op1"
        assert updated.acknowledged_at is not None
        assert updated.acknowledgement_notes == "Verified real threat"

    @pytest.mark.asyncio
    async def test_dismiss_sets_fields(self, config, repo):
        service, _ = make_service(config, repo)
        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)

        updated = await service.dismiss(alert.id, AlertDismiss(user_id="op1", reason="False alarm confirmed"))

        assert updated.status == AlertStatus.DISMISSED
        assert updated.dismissed_by == "op1"
        assert updated.dismissed_at is not None

    @pytest.mark.asyncio
    async def test_double_acknowledge_raises(self, config, repo):
        service, _ = make_service(config, repo)
        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        await service.acknowledge(alert.id, AlertAcknowledge(user_id="op1"))

        with pytest.raises(InvalidAlertTransitionError):
            await service.acknowledge(alert.id, AlertAcknowledge(user_id="op2"))

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_raises(self, config, repo):
        service, _ = make_service(config, repo)
        with pytest.raises(AlertNotFoundError):
            await service.acknowledge(uuid4(), AlertAcknowledge(user_id="op1"))

    @pytest.mark.asyncio
    async def test_dismiss_after_acknowledge_raises(self, config, repo):
        service, _ = make_service(config, repo)
        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        await service.acknowledge(alert.id, AlertAcknowledge(user_id="op1"))

        with pytest.raises(InvalidAlertTransitionError):
            await service.dismiss(alert.id, AlertDismiss(user_id="op1"))


# =============================================================================
# Notification Dispatch
# =============================================================================

class TestNotificationDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_logs_success(self, config, repo):
        provider = FakeProvider(NotificationChannel.CONSOLE)
        service, _ = make_service(config, repo, providers=[provider])

        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)

        logs = await service.get_notification_history(alert.id)
        assert len(logs) == 1
        assert logs[0].status == NotificationStatus.SENT
        assert provider.send_calls == 1
        assert alert.status == AlertStatus.DISPATCHED

    @pytest.mark.asyncio
    async def test_dispatch_to_multiple_channels(self, config, repo):
        console = FakeProvider(NotificationChannel.CONSOLE)
        webhook = FakeProvider(NotificationChannel.WEBHOOK)
        service, _ = make_service(config, repo, providers=[console, webhook])

        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)

        logs = await service.get_notification_history(alert.id)
        assert len(logs) == 2
        channels = {l.channel for l in logs}
        assert channels == {NotificationChannel.CONSOLE, NotificationChannel.WEBHOOK}

    @pytest.mark.asyncio
    async def test_unconfigured_provider_logged_as_failed_not_raised(self, config, repo):
        unconfigured = FakeProvider(NotificationChannel.WEBHOOK, configured=False)
        service, _ = make_service(config, repo, providers=[unconfigured])

        # Must not raise even though the provider isn't configured
        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        assert alert is not None

        logs = await service.get_notification_history(alert.id)
        assert logs[0].status == NotificationStatus.FAILED
        assert "not configured" in logs[0].error_message

    @pytest.mark.asyncio
    async def test_notification_history_for_nonexistent_alert_raises(self, config, repo):
        service, _ = make_service(config, repo)
        with pytest.raises(AlertNotFoundError):
            await service.get_notification_history(uuid4())


# =============================================================================
# Retry Handling
# =============================================================================

class TestRetryHandling:
    @pytest.mark.asyncio
    async def test_failed_delivery_schedules_retry(self, config, repo):
        flaky = FakeProvider(NotificationChannel.WEBHOOK, fail_times=1)
        service, _ = make_service(config, repo, providers=[flaky])

        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        logs = await service.get_notification_history(alert.id)

        assert logs[0].status == NotificationStatus.FAILED
        assert logs[0].next_retry_at is not None
        assert logs[0].attempt_number == 1
        assert logs[0].can_retry is True

    @pytest.mark.asyncio
    async def test_process_retries_succeeds_on_second_attempt(self, repo):
        cfg = AlertConfig(min_severity_for_alert="MEDIUM", enabled_channels=["webhook"], retry_backoff_seconds=1)
        flaky = FakeProvider(NotificationChannel.WEBHOOK, fail_times=1)
        service, dispatcher = make_service(cfg, repo, providers=[flaky])

        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)

        # Force the retry to be due immediately for the test
        logs = await service.get_notification_history(alert.id)
        logs[0].next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await repo.update_notification_log(logs[0])

        retried = await service.process_pending_retries()
        assert len(retried) == 1
        assert retried[0].status == NotificationStatus.SENT
        assert retried[0].attempt_number == 2
        assert flaky.send_calls == 2

    @pytest.mark.asyncio
    async def test_exhausted_retries_stop_scheduling(self, repo):
        cfg = AlertConfig(
            min_severity_for_alert="MEDIUM", enabled_channels=["webhook"],
            max_retry_attempts=2, retry_backoff_seconds=1,
        )
        always_fails = FakeProvider(NotificationChannel.WEBHOOK, fail_times=999)
        service, dispatcher = make_service(cfg, repo, providers=[always_fails])

        alert = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        logs = await service.get_notification_history(alert.id)
        logs[0].next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await repo.update_notification_log(logs[0])

        retried = await service.process_pending_retries()
        assert retried[0].attempt_number == 2
        assert retried[0].status == NotificationStatus.FAILED
        assert retried[0].can_retry is False  # attempt_number == max_attempts
        assert retried[0].next_retry_at is None

        # A further call should find nothing pending (exhausted)
        again = await service.process_pending_retries()
        assert len(again) == 0

    @pytest.mark.asyncio
    async def test_retry_not_due_yet_is_skipped(self, repo):
        cfg = AlertConfig(min_severity_for_alert="MEDIUM", enabled_channels=["webhook"], retry_backoff_seconds=3600)
        flaky = FakeProvider(NotificationChannel.WEBHOOK, fail_times=1)
        service, _ = make_service(cfg, repo, providers=[flaky])

        await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)

        # next_retry_at is ~1 hour out — should not be picked up yet
        retried = await service.process_pending_retries()
        assert len(retried) == 0
        assert flaky.send_calls == 1  # only the initial attempt


# =============================================================================
# Querying / Filtering
# =============================================================================

class TestQueryAndFilter:
    @pytest.mark.asyncio
    async def test_list_all(self, config, repo):
        service, _ = make_service(config, repo)
        await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        await service.create_from_incident(uuid4(), "cam-02", "CRITICAL", "rifle", 90.0)

        alerts = await service.list_alerts()
        assert len(alerts) == 2

    @pytest.mark.asyncio
    async def test_filter_by_severity(self, config, repo):
        service, _ = make_service(config, repo)
        await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        await service.create_from_incident(uuid4(), "cam-02", "CRITICAL", "rifle", 90.0)

        critical = await service.list_alerts(severity="CRITICAL")
        assert len(critical) == 1
        assert critical[0].severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_filter_by_status(self, config, repo):
        service, _ = make_service(config, repo)
        a1 = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        await service.create_from_incident(uuid4(), "cam-02", "HIGH", "knife", 60.0)
        await service.acknowledge(a1.id, AlertAcknowledge(user_id="op1"))

        acknowledged = await service.list_alerts(status=AlertStatus.ACKNOWLEDGED)
        assert len(acknowledged) == 1

    @pytest.mark.asyncio
    async def test_count(self, config, repo):
        service, _ = make_service(config, repo)
        await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        await service.create_from_incident(uuid4(), "cam-02", "HIGH", "knife", 60.0)

        assert await service.count_alerts() == 2
        assert await service.count_alerts(severity="HIGH") == 2

    @pytest.mark.asyncio
    async def test_get_alert(self, config, repo):
        service, _ = make_service(config, repo)
        created = await service.create_from_incident(uuid4(), "cam-01", "HIGH", "handgun", 70.0)
        fetched = await service.get_alert(created.id)
        assert fetched.id == created.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_alert_raises(self, config, repo):
        service, _ = make_service(config, repo)
        with pytest.raises(AlertNotFoundError):
            await service.get_alert(uuid4())


# =============================================================================
# No hard-coded credentials
# =============================================================================

class TestNoHardcodedCredentials:
    def test_default_config_has_empty_credentials(self):
        cfg = AlertConfig()
        assert cfg.webhook_url == ""
        assert cfg.webhook_auth_token == ""
        assert cfg.smtp_password == ""
        assert cfg.smtp_username == ""

    def test_webhook_provider_reports_unconfigured_without_env(self):
        from app.alerts.providers.webhook_provider import WebhookNotificationProvider

        cfg = AlertConfig(webhook_url="")
        provider = WebhookNotificationProvider(cfg)
        assert provider.is_configured is False

    def test_email_provider_reports_unconfigured_without_env(self):
        from app.alerts.providers.email_provider import EmailNotificationProvider

        cfg = AlertConfig(smtp_host="", smtp_from_address="", smtp_recipients=[])
        provider = EmailNotificationProvider(cfg)
        assert provider.is_configured is False

    @pytest.mark.asyncio
    async def test_unconfigured_webhook_fails_cleanly_not_crash(self):
        from app.alerts.providers.webhook_provider import WebhookNotificationProvider
        from app.alerts.models import Alert, AlertSeverity

        cfg = AlertConfig(webhook_url="")
        provider = WebhookNotificationProvider(cfg)
        alert = Alert(
            incident_id=uuid4(), camera_id="cam-01", severity=AlertSeverity.HIGH,
            title="t", message="m",
        )
        result = await provider.send(alert)
        assert result.success is False
        assert "not configured" in result.error_message.lower()


# =============================================================================
# Provider Registry
# =============================================================================

class TestProviderRegistry:
    def test_builds_only_enabled_channels(self):
        from app.alerts.providers import build_providers_from_config

        cfg = AlertConfig(enabled_channels=["console"])
        providers = build_providers_from_config(cfg)
        assert len(providers) == 1
        assert providers[0].channel == NotificationChannel.CONSOLE

    def test_builds_multiple_channels(self):
        from app.alerts.providers import build_providers_from_config

        cfg = AlertConfig(enabled_channels=["console", "webhook", "email"])
        providers = build_providers_from_config(cfg)
        assert len(providers) == 3
        channels = {p.channel for p in providers}
        assert channels == {NotificationChannel.CONSOLE, NotificationChannel.WEBHOOK, NotificationChannel.EMAIL}

    def test_unknown_channel_skipped_not_raised(self):
        from app.alerts.providers import build_providers_from_config

        cfg = AlertConfig(enabled_channels=["console", "carrier_pigeon"])
        providers = build_providers_from_config(cfg)
        assert len(providers) == 1
