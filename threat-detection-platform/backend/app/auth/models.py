"""
Auth Domain Models

Defines users, roles, and permission types.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """System roles with hierarchical permissions."""

    ADMIN = "admin"
    """Full access: user management, configuration, all operations."""

    OPERATOR = "operator"
    """Monitoring and response: view feeds, manage incidents, acknowledge alerts."""

    VIEWER = "viewer"
    """Read-only: view dashboard, incidents, analytics. Cannot modify anything."""


class Permission(str, Enum):
    """Granular permissions checked at endpoint level."""

    # Feed & Monitoring
    VIEW_LIVE_FEED = "view_live_feed"
    CONTROL_STREAMS = "control_streams"

    # Incidents
    VIEW_INCIDENTS = "view_incidents"
    CREATE_INCIDENTS = "create_incidents"
    UPDATE_INCIDENTS = "update_incidents"

    # Alerts
    VIEW_ALERTS = "view_alerts"
    ACKNOWLEDGE_ALERTS = "acknowledge_alerts"

    # Evidence
    VIEW_EVIDENCE = "view_evidence"
    DOWNLOAD_EVIDENCE = "download_evidence"
    DELETE_EVIDENCE = "delete_evidence"
    VIEW_EVIDENCE_AUDIT_LOG = "view_evidence_audit_log"

    # Analytics
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_REPORTS = "export_reports"

    # Cameras
    VIEW_CAMERAS = "view_cameras"
    MANAGE_CAMERAS = "manage_cameras"

    # Users & System
    MANAGE_USERS = "manage_users"
    MANAGE_CONFIG = "manage_config"
    VIEW_AUDIT_LOG = "view_audit_log"


class User(BaseModel):
    """User domain model."""

    id: UUID = Field(default_factory=uuid4)
    email: str
    password_hash: str  # NEVER plaintext
    full_name: str
    role: UserRole = UserRole.VIEWER
    is_active: bool = True

    # Security tracking
    failed_login_count: int = 0
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    def to_safe_dict(self) -> dict:
        """Serialize without sensitive fields (no password_hash)."""
        return {
            "id": str(self.id),
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role.value,
            "is_active": self.is_active,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat(),
        }
