"""
Authentication & Authorization Module

Provides:
- User management (create, lookup, update, deactivate)
- Password hashing (bcrypt, never plaintext)
- JWT token lifecycle (access + refresh)
- Role-based access control (ADMIN, OPERATOR, VIEWER)
- Permission matrix enforcement
- Audit logging for all auth events

Security guarantees:
- Passwords stored as bcrypt hashes only
- JWT tokens are short-lived (access: 30min, refresh: 7 days)
- Token type checked on every validation (access vs refresh)
- Role checked on every protected endpoint
- Failed login attempts tracked
- All auth events written to audit log
"""

from .models import User, UserRole, Permission
from .permissions import PERMISSION_MATRIX, has_permission
from .repository import UserRepository, InMemoryUserRepository
from .service import AuthService
from .audit import AuthAuditLog, AuditAction

__all__ = [
    "User",
    "UserRole",
    "Permission",
    "PERMISSION_MATRIX",
    "has_permission",
    "UserRepository",
    "InMemoryUserRepository",
    "AuthService",
    "AuthAuditLog",
    "AuditAction",
]
