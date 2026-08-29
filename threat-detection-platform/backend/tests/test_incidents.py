"""
Unit tests for the incident management module.

Tests:
- Incident creation
- State machine transitions (valid and invalid)
- Duplicate prevention
- Audit logging
- Querying and filtering
- Validation
"""

import pytest
from uuid import uuid4

from app.incidents import (
    Incident,
    IncidentStatus,
    IncidentCreate,
    IncidentUpdate,
    IncidentService,
    InMemoryIncidentRepository,
)
from app.incidents.exceptions import (
    IncidentNotFoundError,
    InvalidTransitionError,
    DuplicateIncidentError,
)
from app.incidents.models import is_valid_transition, VALID_TRANSITIONS


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def repo():
    return InMemoryIncidentRepository()


@pytest.fixture
def service(repo):
    return IncidentService(repo)


@pytest.fixture
def sample_create():
    return IncidentCreate(
        camera_id="cam-lobby-01",
        threat_type="handgun",
        confidence=0.82,
        risk_score=74.3,
        risk_level="HIGH",
        track_id=5,
        location_name="Main Entrance Lobby",
        location_metadata={"building": "Block A", "floor": "Ground"},
        weapon_count=1,
        frames_confirmed=10,
    )


# =============================================================================
# State Machine Validation Tests
# =============================================================================

class TestStateTransitions:
    """Tests for the incident state machine rules."""

    def test_valid_transitions_from_open(self):
        assert is_valid_transition(IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED) is True
        assert is_valid_transition(IncidentStatus.OPEN, IncidentStatus.RESOLVED) is True
        assert is_valid_transition(IncidentStatus.OPEN, IncidentStatus.FALSE_POSITIVE) is True

    def test_valid_transitions_from_acknowledged(self):
        assert is_valid_transition(IncidentStatus.ACKNOWLEDGED, IncidentStatus.RESOLVED) is True
        assert is_valid_transition(IncidentStatus.ACKNOWLEDGED, IncidentStatus.FALSE_POSITIVE) is True

    def test_invalid_transition_backward(self):
        assert is_valid_transition(IncidentStatus.ACKNOWLEDGED, IncidentStatus.OPEN) is False

    def test_resolved_is_terminal(self):
        assert is_valid_transition(IncidentStatus.RESOLVED, IncidentStatus.OPEN) is False
        assert is_valid_transition(IncidentStatus.RESOLVED, IncidentStatus.ACKNOWLEDGED) is False
        assert is_valid_transition(IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE) is False

    def test_false_positive_is_terminal(self):
        assert is_valid_transition(IncidentStatus.FALSE_POSITIVE, IncidentStatus.OPEN) is False
        assert is_valid_transition(IncidentStatus.FALSE_POSITIVE, IncidentStatus.RESOLVED) is False

    def test_same_state_transition_invalid(self):
        assert is_valid_transition(IncidentStatus.OPEN, IncidentStatus.OPEN) is False


# =============================================================================
# Incident Creation Tests
# =============================================================================

class TestIncidentCreation:
    """Tests for creating incidents."""

    @pytest.mark.asyncio
    async def test_create_incident(self, service, sample_create):
        incident = await service.create_incident(sample_create)

        assert incident.id is not None
        assert incident.incident_number == 1
        assert incident.camera_id == "cam-lobby-01"
        assert incident.threat_type == "handgun"
        assert incident.confidence == 0.82
        assert incident.risk_score == 74.3
        assert incident.risk_level == "HIGH"
        assert incident.status == IncidentStatus.OPEN
        assert incident.track_id == 5
        assert incident.location_name == "Main Entrance Lobby"
        assert incident.weapon_count == 1
        assert incident.frames_confirmed == 10

    @pytest.mark.asyncio
    async def test_sequential_numbering(self, service, sample_create):
        i1 = await service.create_incident(sample_create)
        sample_create.track_id = 6  # Different track
        i2 = await service.create_incident(sample_create)
        sample_create.track_id = 7
        i3 = await service.create_incident(sample_create)

        assert i1.incident_number == 1
        assert i2.incident_number == 2
        assert i3.incident_number == 3

    @pytest.mark.asyncio
    async def test_create_sets_timestamps(self, service, sample_create):
        incident = await service.create_incident(sample_create)

        assert incident.created_at is not None
        assert incident.updated_at is not None
        assert incident.acknowledged_at is None
        assert incident.resolved_at is None

    @pytest.mark.asyncio
    async def test_create_generates_description(self, service, sample_create):
        sample_create.description = ""
        incident = await service.create_incident(sample_create)

        assert "handgun" in incident.description.lower() or "Handgun" in incident.description
        assert "cam-lobby-01" in incident.description

    @pytest.mark.asyncio
    async def test_create_with_explicit_description(self, service, sample_create):
        sample_create.description = "Custom description"
        incident = await service.create_incident(sample_create)
        assert incident.description == "Custom description"

    @pytest.mark.asyncio
    async def test_duplicate_track_prevention(self, service, sample_create):
        await service.create_incident(sample_create)

        with pytest.raises(DuplicateIncidentError):
            await service.create_incident(sample_create)  # Same track_id=5

    @pytest.mark.asyncio
    async def test_duplicate_allowed_after_resolution(self, service, sample_create):
        incident = await service.create_incident(sample_create)

        # Resolve the first incident
        await service.update_status(
            incident.id,
            IncidentUpdate(status=IncidentStatus.RESOLVED, user_id="op1"),
        )

        # Now creating another for same track should succeed
        new_incident = await service.create_incident(sample_create)
        assert new_incident.id != incident.id

    @pytest.mark.asyncio
    async def test_no_track_id_allows_multiple(self, service):
        """Incidents without track_id don't trigger duplicate check."""
        data = IncidentCreate(
            camera_id="cam-01",
            threat_type="knife",
            confidence=0.7,
            risk_score=45.0,
            risk_level="MEDIUM",
            track_id=None,
        )
        i1 = await service.create_incident(data)
        i2 = await service.create_incident(data)
        assert i1.id != i2.id


# =============================================================================
# Status Update Tests
# =============================================================================

class TestStatusUpdates:
    """Tests for status transition operations."""

    @pytest.mark.asyncio
    async def test_acknowledge_incident(self, service, sample_create):
        incident = await service.create_incident(sample_create)

        updated = await service.update_status(
            incident.id,
            IncidentUpdate(status=IncidentStatus.ACKNOWLEDGED, user_id="operator1"),
        )

        assert updated.status == IncidentStatus.ACKNOWLEDGED
        assert updated.acknowledged_at is not None
        assert updated.acknowledged_by == "operator1"

    @pytest.mark.asyncio
    async def test_resolve_incident(self, service, sample_create):
        incident = await service.create_incident(sample_create)

        # Acknowledge first
        await service.update_status(
            incident.id,
            IncidentUpdate(status=IncidentStatus.ACKNOWLEDGED, user_id="op1"),
        )

        # Then resolve
        updated = await service.update_status(
            incident.id,
            IncidentUpdate(
                status=IncidentStatus.RESOLVED,
                user_id="op1",
                notes="Threat neutralized by security team",
            ),
        )

        assert updated.status == IncidentStatus.RESOLVED
        assert updated.resolved_at is not None
        assert updated.resolved_by == "op1"
        assert updated.resolution_notes == "Threat neutralized by security team"

    @pytest.mark.asyncio
    async def test_mark_false_positive(self, service, sample_create):
        incident = await service.create_incident(sample_create)

        updated = await service.update_status(
            incident.id,
            IncidentUpdate(
                status=IncidentStatus.FALSE_POSITIVE,
                user_id="op1",
                notes="Object was a toy gun",
            ),
        )

        assert updated.status == IncidentStatus.FALSE_POSITIVE
        assert updated.resolution_notes == "Object was a toy gun"

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self, service, sample_create):
        incident = await service.create_incident(sample_create)

        # Resolve it
        await service.update_status(
            incident.id,
            IncidentUpdate(status=IncidentStatus.RESOLVED, user_id="op1"),
        )

        # Try to go back to OPEN — should fail
        with pytest.raises(InvalidTransitionError):
            await service.update_status(
                incident.id,
                IncidentUpdate(status=IncidentStatus.OPEN),
            )

    @pytest.mark.asyncio
    async def test_update_nonexistent_incident(self, service):
        fake_id = uuid4()
        with pytest.raises(IncidentNotFoundError):
            await service.update_status(
                fake_id,
                IncidentUpdate(status=IncidentStatus.ACKNOWLEDGED),
            )

    @pytest.mark.asyncio
    async def test_direct_open_to_resolved(self, service, sample_create):
        """OPEN → RESOLVED is allowed (skip acknowledge)."""
        incident = await service.create_incident(sample_create)

        updated = await service.update_status(
            incident.id,
            IncidentUpdate(status=IncidentStatus.RESOLVED, user_id="op1"),
        )
        assert updated.status == IncidentStatus.RESOLVED


# =============================================================================
# Audit Log Tests
# =============================================================================

class TestAuditLog:
    """Tests for audit trail."""

    @pytest.mark.asyncio
    async def test_creation_is_audited(self, service, sample_create):
        incident = await service.create_incident(sample_create)
        log = await service.get_audit_log(incident.id)

        assert len(log) == 1
        assert log[0].action == "incident_created"
        assert log[0].new_value == "OPEN"

    @pytest.mark.asyncio
    async def test_status_change_is_audited(self, service, sample_create):
        incident = await service.create_incident(sample_create)

        await service.update_status(
            incident.id,
            IncidentUpdate(status=IncidentStatus.ACKNOWLEDGED, user_id="op1"),
        )

        log = await service.get_audit_log(incident.id)
        assert len(log) == 2
        assert log[1].action == "status_changed"
        assert log[1].old_value == "OPEN"
        assert log[1].new_value == "ACKNOWLEDGED"
        assert log[1].user_id == "op1"

    @pytest.mark.asyncio
    async def test_full_lifecycle_audit(self, service, sample_create):
        incident = await service.create_incident(sample_create)

        await service.update_status(
            incident.id,
            IncidentUpdate(status=IncidentStatus.ACKNOWLEDGED, user_id="op1"),
        )
        await service.update_status(
            incident.id,
            IncidentUpdate(status=IncidentStatus.RESOLVED, user_id="op1", notes="Done"),
        )

        log = await service.get_audit_log(incident.id)
        assert len(log) == 3
        actions = [e.action for e in log]
        assert actions == ["incident_created", "status_changed", "status_changed"]

    @pytest.mark.asyncio
    async def test_audit_log_for_nonexistent_raises(self, service):
        with pytest.raises(IncidentNotFoundError):
            await service.get_audit_log(uuid4())


# =============================================================================
# Query Tests
# =============================================================================

class TestQueryAndFilter:
    """Tests for listing and filtering incidents."""

    @pytest.mark.asyncio
    async def test_list_all(self, service, sample_create):
        await service.create_incident(sample_create)
        sample_create.track_id = 10
        await service.create_incident(sample_create)

        incidents = await service.list_incidents()
        assert len(incidents) == 2

    @pytest.mark.asyncio
    async def test_filter_by_status(self, service, sample_create):
        i1 = await service.create_incident(sample_create)
        sample_create.track_id = 10
        i2 = await service.create_incident(sample_create)

        # Acknowledge one
        await service.update_status(
            i1.id, IncidentUpdate(status=IncidentStatus.ACKNOWLEDGED, user_id="op1")
        )

        open_incidents = await service.list_incidents(status=IncidentStatus.OPEN)
        assert len(open_incidents) == 1
        assert open_incidents[0].id == i2.id

    @pytest.mark.asyncio
    async def test_filter_by_camera(self, service):
        d1 = IncidentCreate(camera_id="cam-A", threat_type="knife", confidence=0.7, risk_score=40, risk_level="MEDIUM")
        d2 = IncidentCreate(camera_id="cam-B", threat_type="rifle", confidence=0.9, risk_score=80, risk_level="HIGH")

        await service.create_incident(d1)
        await service.create_incident(d2)

        cam_a = await service.list_incidents(camera_id="cam-A")
        assert len(cam_a) == 1
        assert cam_a[0].camera_id == "cam-A"

    @pytest.mark.asyncio
    async def test_filter_by_risk_level(self, service):
        d1 = IncidentCreate(camera_id="cam-1", threat_type="knife", confidence=0.5, risk_score=30, risk_level="LOW")
        d2 = IncidentCreate(camera_id="cam-1", threat_type="rifle", confidence=0.9, risk_score=85, risk_level="CRITICAL", track_id=2)

        await service.create_incident(d1)
        await service.create_incident(d2)

        critical = await service.list_incidents(risk_level="CRITICAL")
        assert len(critical) == 1
        assert critical[0].risk_level == "CRITICAL"

    @pytest.mark.asyncio
    async def test_pagination(self, service):
        for i in range(10):
            data = IncidentCreate(
                camera_id="cam-1", threat_type="handgun",
                confidence=0.8, risk_score=70, risk_level="HIGH", track_id=i+100,
            )
            await service.create_incident(data)

        page1 = await service.list_incidents(limit=3, offset=0)
        page2 = await service.list_incidents(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].id != page2[0].id

    @pytest.mark.asyncio
    async def test_count(self, service, sample_create):
        await service.create_incident(sample_create)
        sample_create.track_id = 20
        await service.create_incident(sample_create)

        count = await service.count_incidents()
        assert count == 2

        count_open = await service.count_incidents(status=IncidentStatus.OPEN)
        assert count_open == 2

    @pytest.mark.asyncio
    async def test_get_incident_by_id(self, service, sample_create):
        created = await service.create_incident(sample_create)
        retrieved = await service.get_incident(created.id)
        assert retrieved.id == created.id
        assert retrieved.threat_type == "handgun"

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self, service):
        with pytest.raises(IncidentNotFoundError):
            await service.get_incident(uuid4())

    @pytest.mark.asyncio
    async def test_has_active_incident_for_track(self, service, sample_create):
        await service.create_incident(sample_create)
        assert await service.has_active_incident_for_track(5) is True
        assert await service.has_active_incident_for_track(999) is False
