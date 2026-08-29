"""
Incident Repository (Data Access Layer)

Defines the abstract repository interface and an in-memory implementation.
The in-memory implementation enables testing without a database.
A SQLAlchemy implementation can be added later for production.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from .models import AuditEntry, Incident, IncidentStatus


class IncidentRepository(ABC):
    """
    Abstract repository interface for incidents.

    Any persistence backend (in-memory, PostgreSQL, etc.) must implement this.
    """

    @abstractmethod
    async def create(self, incident: Incident) -> Incident:
        """Persist a new incident. Returns the incident with assigned number."""
        ...

    @abstractmethod
    async def get_by_id(self, incident_id: UUID) -> Optional[Incident]:
        """Retrieve an incident by ID. Returns None if not found."""
        ...

    @abstractmethod
    async def update(self, incident: Incident) -> Incident:
        """Persist updated incident state."""
        ...

    @abstractmethod
    async def list_all(
        self,
        status: Optional[IncidentStatus] = None,
        camera_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        """List incidents with optional filters and pagination."""
        ...

    @abstractmethod
    async def count(
        self,
        status: Optional[IncidentStatus] = None,
        camera_id: Optional[str] = None,
    ) -> int:
        """Count incidents matching filters."""
        ...

    @abstractmethod
    async def get_active_by_track_id(self, track_id: int) -> Optional[Incident]:
        """Find an active (non-terminal) incident for a given track ID."""
        ...

    @abstractmethod
    async def add_audit_entry(self, entry: AuditEntry) -> AuditEntry:
        """Persist an audit log entry."""
        ...

    @abstractmethod
    async def get_audit_log(self, incident_id: UUID) -> List[AuditEntry]:
        """Get all audit entries for an incident, ordered by timestamp."""
        ...


class InMemoryIncidentRepository(IncidentRepository):
    """
    In-memory implementation for testing and development.

    Data is lost when the process stops. Not for production.
    """

    def __init__(self):
        self._incidents: Dict[UUID, Incident] = {}
        self._audit_log: List[AuditEntry] = []
        self._next_number: int = 1

    async def create(self, incident: Incident) -> Incident:
        incident.incident_number = self._next_number
        self._next_number += 1
        self._incidents[incident.id] = incident
        return incident

    async def get_by_id(self, incident_id: UUID) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    async def update(self, incident: Incident) -> Incident:
        incident.updated_at = datetime.now(timezone.utc)
        self._incidents[incident.id] = incident
        return incident

    async def list_all(
        self,
        status: Optional[IncidentStatus] = None,
        camera_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        results = list(self._incidents.values())

        # Apply filters
        if status:
            results = [i for i in results if i.status == status]
        if camera_id:
            results = [i for i in results if i.camera_id == camera_id]
        if risk_level:
            results = [i for i in results if i.risk_level == risk_level]

        # Sort by created_at descending (newest first)
        results.sort(key=lambda i: i.created_at, reverse=True)

        # Paginate
        return results[offset:offset + limit]

    async def count(
        self,
        status: Optional[IncidentStatus] = None,
        camera_id: Optional[str] = None,
    ) -> int:
        results = list(self._incidents.values())
        if status:
            results = [i for i in results if i.status == status]
        if camera_id:
            results = [i for i in results if i.camera_id == camera_id]
        return len(results)

    async def get_active_by_track_id(self, track_id: int) -> Optional[Incident]:
        terminal_states = {IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE}
        for incident in self._incidents.values():
            if incident.track_id == track_id and incident.status not in terminal_states:
                return incident
        return None

    async def add_audit_entry(self, entry: AuditEntry) -> AuditEntry:
        self._audit_log.append(entry)
        return entry

    async def get_audit_log(self, incident_id: UUID) -> List[AuditEntry]:
        entries = [e for e in self._audit_log if e.incident_id == incident_id]
        entries.sort(key=lambda e: e.timestamp)
        return entries

    def clear(self):
        """Clear all data (for testing)."""
        self._incidents.clear()
        self._audit_log.clear()
        self._next_number = 1
