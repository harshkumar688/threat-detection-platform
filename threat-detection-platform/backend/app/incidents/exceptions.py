"""
Incident-specific exceptions.
"""


class IncidentError(Exception):
    """Base exception for incident operations."""
    pass


class IncidentNotFoundError(IncidentError):
    """Raised when an incident ID does not exist."""

    def __init__(self, incident_id):
        self.incident_id = incident_id
        super().__init__(f"Incident not found: {incident_id}")


class InvalidTransitionError(IncidentError):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, from_status, to_status):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid transition: {from_status.value} → {to_status.value}. "
            f"Allowed from {from_status.value}: "
            f"{[s.value for s in from_status.__class__ if s.value != from_status.value]}"
        )


class DuplicateIncidentError(IncidentError):
    """Raised when trying to create a duplicate incident for an active track."""

    def __init__(self, track_id):
        self.track_id = track_id
        super().__init__(f"Active incident already exists for track_id: {track_id}")
