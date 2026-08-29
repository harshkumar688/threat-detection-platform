"""
API Dependencies

FastAPI dependency injection providers for:
- Authentication (JWT token → user context)
- Authorization (role enforcement)
- Pagination parameters
- Service instances

These are injected via Depends() in route handlers.
"""

from typing import Optional

from fastapi import Depends, Header, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import Permission, UserRole
from app.auth.permissions import has_permission
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.schemas.base import PaginationParams

# Bearer token extractor
security_scheme = HTTPBearer(auto_error=False)


# =============================================================================
# Authentication
# =============================================================================

class CurrentUser:
    """Represents the authenticated user from JWT."""

    def __init__(self, user_id: str, email: str = "", role: str = "viewer"):
        self.user_id = user_id
        self.email = email
        self.role = role

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_operator(self) -> bool:
        return self.role in ("admin", "operator")

    @property
    def is_viewer(self) -> bool:
        return self.role in ("admin", "operator", "viewer")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> CurrentUser:
    """
    Extract and validate JWT from Authorization header.

    Returns CurrentUser context. Raises 401 if invalid/missing.
    """
    if credentials is None:
        raise UnauthorizedError("Authentication required")

    payload = decode_token(credentials.credentials)
    if payload is None:
        raise UnauthorizedError("Invalid or expired token")

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type")

    return CurrentUser(
        user_id=payload.get("sub", ""),
        email=payload.get("email", ""),
        role=payload.get("role", "viewer"),
    )


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Require admin role. Raises 403 if not admin."""
    if not user.is_admin:
        raise ForbiddenError("Admin access required")
    return user


async def require_operator(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Require operator or admin role. Raises 403 if viewer."""
    if not user.is_operator:
        raise ForbiddenError("Operator access required")
    return user


def require_permission(permission: Permission):
    """
    Build a dependency that enforces a specific permission from the
    single-source-of-truth PERMISSION_MATRIX (app.auth.permissions).

    Usage:
        @router.get("/x", dependencies=[Depends(require_permission(Permission.DOWNLOAD_EVIDENCE))])
    """

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        try:
            role = UserRole(user.role)
        except ValueError:
            raise ForbiddenError("Unknown role")

        if not has_permission(role, permission):
            raise ForbiddenError(f"Missing required permission: {permission.value}")
        return user

    return _check


# =============================================================================
# Pagination
# =============================================================================

def get_pagination(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """Extract pagination parameters from query string."""
    return PaginationParams(page=page, page_size=page_size)
