"""
Incident Management Module

Handles the full lifecycle of security incidents:
- Creation from confirmed threats
- State transitions (OPEN → ACKNOWLEDGED → RESOLVED / FALSE_POSITIVE)
- Validation of state machine rules
- Audit logging
- Query and filtering

Architecture:
    ┌───────────────────┐
    │  API Router       │  ← HTTP endpoints (implemented separately)
    └─────────┬─────────┘
              │
    ┌─────────▼─────────┐
    │  IncidentService  │  ← Business logic, validation, state machine
    └─────────┬─────────┘
              │
    ┌─────────▼─────────┐
    │  IncidentRepo     │  ← Data persistence (repository pattern)
    └───────────────────┘

The repository is abstract — can be backed by:
- InMemoryIncidentRepository (for testing / dev without DB)
- SQLAlchemyIncidentRepository (production with PostgreSQL)
"""

from .models import Incident, IncidentStatus, IncidentCreate, IncidentUpdate, AuditEntry
from .service import IncidentService
from .repository import IncidentRepository, InMemoryIncidentRepository

__all__ = [
    "Incident",
    "IncidentStatus",
    "IncidentCreate",
    "IncidentUpdate",
    "AuditEntry",
    "IncidentService",
    "IncidentRepository",
    "InMemoryIncidentRepository",
]
