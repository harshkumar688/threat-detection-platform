"""
Alert-specific exceptions.
"""


class AlertError(Exception):
    """Base exception for alert operations."""
    pass


class AlertNotFoundError(AlertError):
    """Raised when an alert ID does not exist."""

    def __init__(self, alert_id):
        self.alert_id = alert_id
        super().__init__(f"Alert not found: {alert_id}")


class InvalidAlertTransitionError(AlertError):
    """Raised when an invalid alert status transition is attempted."""

    def __init__(self, from_status, to_status):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Invalid alert transition: {from_status.value} → {to_status.value}")


class DuplicateAlertError(AlertError):
    """Raised when an active alert already exists for the given incident."""

    def __init__(self, incident_id):
        self.incident_id = incident_id
        super().__init__(f"Active alert already exists for incident: {incident_id}")


class BelowAlertThresholdError(AlertError):
    """Raised when the incident's severity does not meet the minimum alert threshold."""

    def __init__(self, risk_level: str, min_level: str):
        self.risk_level = risk_level
        self.min_level = min_level
        super().__init__(
            f"Incident risk level '{risk_level}' is below the minimum alert threshold '{min_level}'"
        )
