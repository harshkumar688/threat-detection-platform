"""
Auth Audit Log

Records all authentication and authorization events:
- Login success/failure
- Token refresh
- Account lockout
- Role changes
- Password changes
- Permission denials

Append-only log — entries cannot be modified or deleted.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    """Authentication audit event types."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGIN_LOCKED = "login_locked"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    REGISTER = "register"
    PASSWORD_CHANGED = "password_changed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    ACCOUNT_ACTIVATED = "account_activated"
    ROLE_CHANGED = "role_changed"
    PERMISSION_DENIED = "permission_denied"


class AuthAuditEntry(BaseModel):
    """Single audit log entry."""

    id: UUID = Field(default_factory=uuid4)
    action: AuditAction
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class AuthAuditLog:
    """
    Append-only audit log for auth events.

    In production, this writes to PostgreSQL.
    This implementation is in-memory for testing.
    """

    def __init__(self):
        self._entries: List[AuthAuditEntry] = []

    def log(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[str] = None,
    ) -> AuthAuditEntry:
        """Record an audit event. Returns the created entry."""
        entry = AuthAuditEntry(
            action=action,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            details=details,
        )
        self._entries.append(entry)
        return entry

    def get_entries(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        limit: int = 100,
    ) -> List[AuthAuditEntry]:
        """Query audit entries with optional filters."""
        results = self._entries

        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if action:
            results = [e for e in results if e.action == action]

        # Most recent first
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_failed_logins(self, user_email: str, since_minutes: int = 15) -> int:
        """Count recent failed login attempts for an email."""
        cutoff = datetime.now(timezone.utc)
        from datetime import timedelta
        cutoff = cutoff - timedelta(minutes=since_minutes)

        return sum(
            1 for e in self._entries
            if e.action == AuditAction.LOGIN_FAILED
            and e.user_email == user_email
            and e.timestamp > cutoff
        )

    @property
    def total_entries(self) -> int:
        return len(self._entries)

    def clear(self):
        """Clear log (testing only)."""
        self._entries.clear()
