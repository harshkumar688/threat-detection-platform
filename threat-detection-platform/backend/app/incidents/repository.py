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


class SqlIncidentRepository(IncidentRepository):
    """
    Durable incident repository backed by the generic document store
    (SQLite by default, PostgreSQL via DATABASE_URL). Persists Incident and
    AuditEntry Pydantic models as JSON documents, so data survives restarts.

    Filtering/pagination is done in Python after loading — acceptable for the
    prototype's data volumes and keeps the storage layer generic. A
    production PostgreSQL build could push these into SQL later without
    changing this class's public interface.
    """

    def __init__(self):
        from app.db import DocumentStore

        self._incidents = DocumentStore("incident")
        self._audit = DocumentStore("incident_audit")

    async def create(self, incident: Incident) -> Incident:
        # seq assigned by the store becomes the human-readable incident_number.
        payload = incident.model_dump(mode="json")
        seq = await self._incidents.upsert(str(incident.id), payload, seq=None)
        incident.incident_number = seq
        # Persist again with the assigned number embedded in the payload.
        await self._incidents.upsert(str(incident.id), incident.model_dump(mode="json"), seq=seq)
        return incident

    async def get_by_id(self, incident_id: UUID) -> Optional[Incident]:
        data = await self._incidents.get(str(incident_id))
        if data is None:
            return None
        return self._to_incident(data)

    async def update(self, incident: Incident) -> Incident:
        incident.updated_at = datetime.now(timezone.utc)
        await self._incidents.upsert(
            str(incident.id), incident.model_dump(mode="json"), seq=incident.incident_number
        )
        return incident

    async def list_all(
        self,
        status: Optional[IncidentStatus] = None,
        camera_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        rows = await self._incidents.list_all()
        results = [self._to_incident(d) for d in rows]

        if status:
            results = [i for i in results if i.status == status]
        if camera_id:
            results = [i for i in results if i.camera_id == camera_id]
        if risk_level:
            results = [i for i in results if i.risk_level == risk_level]

        results.sort(key=lambda i: i.created_at, reverse=True)
        return results[offset:offset + limit]

    async def count(
        self,
        status: Optional[IncidentStatus] = None,
        camera_id: Optional[str] = None,
    ) -> int:
        rows = await self._incidents.list_all()
        results = [self._to_incident(d) for d in rows]
        if status:
            results = [i for i in results if i.status == status]
        if camera_id:
            results = [i for i in results if i.camera_id == camera_id]
        return len(results)

    async def get_active_by_track_id(self, track_id: int) -> Optional[Incident]:
        terminal_states = {IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE}
        rows = await self._incidents.list_all()
        for data in rows:
            incident = self._to_incident(data)
            if incident.track_id == track_id and incident.status not in terminal_states:
                return incident
        return None

    async def add_audit_entry(self, entry: AuditEntry) -> AuditEntry:
        await self._audit.upsert(str(entry.id), entry.model_dump(mode="json"), seq=None)
        return entry

    async def get_audit_log(self, incident_id: UUID) -> List[AuditEntry]:
        rows = await self._audit.list_all()
        entries = [AuditEntry(**{k: v for k, v in d.items() if k != "_seq"}) for d in rows]
        entries = [e for e in entries if e.incident_id == incident_id]
        entries.sort(key=lambda e: e.timestamp)
        return entries

    @staticmethod
    def _to_incident(data: dict) -> Incident:
        clean = {k: v for k, v in data.items() if k != "_seq"}
        return Incident(**clean)

    async def clear(self):
        await self._incidents.clear()
        await self._audit.clear()
