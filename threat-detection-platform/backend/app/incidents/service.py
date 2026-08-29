"""
Incident Service

Business logic layer for incident management:
- Creates incidents from confirmed threats
- Validates and enforces state machine transitions
- Writes audit log entries for every action
- Prevents duplicate incidents for the same active track
- Provides querying and filtering

This service is the single point of entry for all incident operations.
Routers and other modules call this — never the repository directly.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from .exceptions import (
    DuplicateIncidentError,
    IncidentNotFoundError,
    InvalidTransitionError,
)
from .models import (
    AuditEntry,
    Incident,
    IncidentCreate,
    IncidentStatus,
    IncidentUpdate,
    is_valid_transition,
)
from .repository import IncidentRepository

logger = logging.getLogger(__name__)


class IncidentService:
    """
    Incident management service.

    Usage:
        repo = InMemoryIncidentRepository()  # or SQLAlchemy repo
        service = IncidentService(repo)

        # Create from confirmed threat
        incident = await service.create_incident(IncidentCreate(...))

        # Update status
        incident = await service.update_status(
            incident.id, IncidentUpdate(status=IncidentStatus.ACKNOWLEDGED, user_id="op1")
        )
    """

    def __init__(self, repository: IncidentRepository):
        """
        Initialize with a repository implementation.

        Args:
            repository: Any IncidentRepository implementation.
        """
        self._repo = repository

    async def create_incident(self, data: IncidentCreate) -> Incident:
        """
        Create a new incident from confirmed threat data.

        Validates:
        - No active incident already exists for this track_id (if provided)

        Args:
            data: IncidentCreate DTO with threat details.

        Returns:
            Created Incident with assigned ID and number.

        Raises:
            DuplicateIncidentError: If an active incident exists for the track.
        """
        # Check for duplicate active incident on same track
        if data.track_id is not None:
            existing = await self._repo.get_active_by_track_id(data.track_id)
            if existing is not None:
                raise DuplicateIncidentError(data.track_id)

        # Build incident
        now = datetime.now(timezone.utc)
        incident = Incident(
            camera_id=data.camera_id,
            threat_type=data.threat_type,
            confidence=data.confidence,
            risk_score=data.risk_score,
            risk_level=data.risk_level,
            track_id=data.track_id,
            location_id=data.location_id,
            location_name=data.location_name,
            building=data.building,
            zone=data.zone,
            latitude=data.latitude,
            longitude=data.longitude,
            location_metadata=data.location_metadata,
            status=IncidentStatus.OPEN,
            weapon_count=data.weapon_count,
            frames_confirmed=data.frames_confirmed,
            description=data.description or self._generate_description(data),
            created_at=now,
            updated_at=now,
        )

        # Persist
        incident = await self._repo.create(incident)

        # Audit
        await self._audit(
            incident_id=incident.id,
            action="incident_created",
            new_value=IncidentStatus.OPEN.value,
            notes=f"Threat: {data.threat_type}, Risk: {data.risk_level} ({data.risk_score:.1f})",
        )

        logger.info(
            "Incident created: #%d [%s] %s (risk=%s, score=%.1f)",
            incident.incident_number,
            incident.id,
            data.threat_type,
            data.risk_level,
            data.risk_score,
        )

        return incident

    async def get_incident(self, incident_id: UUID) -> Incident:
        """
        Retrieve an incident by ID.

        Raises:
            IncidentNotFoundError: If not found.
        """
        incident = await self._repo.get_by_id(incident_id)
        if incident is None:
            raise IncidentNotFoundError(incident_id)
        return incident

    async def update_status(self, incident_id: UUID, update: IncidentUpdate) -> Incident:
        """
        Transition an incident to a new status.

        Validates:
        - Incident exists
        - Transition is allowed by state machine
        - Required fields are present (user_id for acknowledge/resolve)

        Args:
            incident_id: ID of the incident to update.
            update: IncidentUpdate with new status and metadata.

        Returns:
            Updated Incident.

        Raises:
            IncidentNotFoundError: If incident not found.
            InvalidTransitionError: If transition is not allowed.
        """
        incident = await self._repo.get_by_id(incident_id)
        if incident is None:
            raise IncidentNotFoundError(incident_id)

        # Validate transition
        if not is_valid_transition(incident.status, update.status):
            raise InvalidTransitionError(incident.status, update.status)

        old_status = incident.status
        now = datetime.now(timezone.utc)

        # Apply transition
        incident.status = update.status
        incident.updated_at = now

        if update.status == IncidentStatus.ACKNOWLEDGED:
            incident.acknowledged_at = now
            incident.acknowledged_by = update.user_id

        elif update.status in (IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE):
            incident.resolved_at = now
            incident.resolved_by = update.user_id
            incident.resolution_notes = update.notes

        # Persist
        incident = await self._repo.update(incident)

        # Audit
        await self._audit(
            incident_id=incident.id,
            action="status_changed",
            old_value=old_status.value,
            new_value=update.status.value,
            user_id=update.user_id,
            notes=update.notes,
        )

        logger.info(
            "Incident #%d status: %s → %s (by %s)",
            incident.incident_number,
            old_status.value,
            update.status.value,
            update.user_id or "system",
        )

        return incident

    async def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        camera_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        """
        List incidents with optional filtering and pagination.

        Args:
            status: Filter by status.
            camera_id: Filter by camera.
            risk_level: Filter by risk level.
            limit: Max results to return.
            offset: Pagination offset.

        Returns:
            List of incidents sorted by created_at descending.
        """
        return await self._repo.list_all(
            status=status,
            camera_id=camera_id,
            risk_level=risk_level,
            limit=limit,
            offset=offset,
        )

    async def count_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        camera_id: Optional[str] = None,
    ) -> int:
        """Count incidents matching filters."""
        return await self._repo.count(status=status, camera_id=camera_id)

    async def get_audit_log(self, incident_id: UUID) -> List[AuditEntry]:
        """
        Get the full audit trail for an incident.

        Raises:
            IncidentNotFoundError: If incident not found.
        """
        incident = await self._repo.get_by_id(incident_id)
        if incident is None:
            raise IncidentNotFoundError(incident_id)
        return await self._repo.get_audit_log(incident_id)

    async def has_active_incident_for_track(self, track_id: int) -> bool:
        """Check if an active incident exists for a given track."""
        existing = await self._repo.get_active_by_track_id(track_id)
        return existing is not None

    async def _audit(
        self,
        incident_id: UUID,
        action: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Write an audit log entry."""
        entry = AuditEntry(
            incident_id=incident_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            user_id=user_id,
            notes=notes,
        )
        await self._repo.add_audit_entry(entry)

    @staticmethod
    def _generate_description(data: IncidentCreate) -> str:
        """Auto-generate incident description from creation data."""
        parts = [
            f"{data.threat_type.capitalize()} detected",
            f"on camera '{data.camera_id}'",
        ]
        if data.location_name:
            parts.append(f"at {data.location_name}")
        parts.append(f"with {data.confidence:.0%} confidence")
        parts.append(f"(risk: {data.risk_level}, score: {data.risk_score:.1f}/100)")
        return " ".join(parts)
