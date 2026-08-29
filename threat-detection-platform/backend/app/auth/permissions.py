"""
Permission Matrix

Defines which roles have which permissions.
This is the SINGLE SOURCE OF TRUTH for access control.

Every protected endpoint checks against this matrix.
No permission logic is scattered across routers.
"""

from typing import Set

from .models import Permission, UserRole


# =============================================================================
# Permission Matrix
# =============================================================================

PERMISSION_MATRIX: dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: {
        # Admin gets everything
        Permission.VIEW_LIVE_FEED,
        Permission.CONTROL_STREAMS,
        Permission.VIEW_INCIDENTS,
        Permission.CREATE_INCIDENTS,
        Permission.UPDATE_INCIDENTS,
        Permission.VIEW_ALERTS,
        Permission.ACKNOWLEDGE_ALERTS,
        Permission.VIEW_EVIDENCE,
        Permission.DOWNLOAD_EVIDENCE,
        Permission.DELETE_EVIDENCE,
        Permission.VIEW_EVIDENCE_AUDIT_LOG,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_REPORTS,
        Permission.VIEW_CAMERAS,
        Permission.MANAGE_CAMERAS,
        Permission.MANAGE_USERS,
        Permission.MANAGE_CONFIG,
        Permission.VIEW_AUDIT_LOG,
    },

    UserRole.OPERATOR: {
        # Operator: monitoring + response, no user/config management.
        # Can download evidence files (needed for incident response), but
        # cannot view the evidence access audit trail (admin-only).
        Permission.VIEW_LIVE_FEED,
        Permission.CONTROL_STREAMS,
        Permission.VIEW_INCIDENTS,
        Permission.CREATE_INCIDENTS,
        Permission.UPDATE_INCIDENTS,
        Permission.VIEW_ALERTS,
        Permission.ACKNOWLEDGE_ALERTS,
        Permission.VIEW_EVIDENCE,
        Permission.DOWNLOAD_EVIDENCE,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_REPORTS,
        Permission.VIEW_CAMERAS,
    },

    UserRole.VIEWER: {
        # Viewer: read-only access. Can see that evidence exists (metadata:
        # type, size, capture time) but CANNOT download the actual media
        # file — evidence access is restricted to roles that need it for
        # incident response, not general browsing.
        Permission.VIEW_LIVE_FEED,
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_ALERTS,
        Permission.VIEW_EVIDENCE,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_REPORTS,
        Permission.VIEW_CAMERAS,
    },
}


def has_permission(role: UserRole, permission: Permission) -> bool:
    """
    Check if a role has a specific permission.

    Args:
        role: User's role.
        permission: Required permission.

    Returns:
        True if the role grants this permission.
    """
    role_permissions = PERMISSION_MATRIX.get(role, set())
    return permission in role_permissions


def get_permissions_for_role(role: UserRole) -> Set[Permission]:
    """Get all permissions for a role."""
    return PERMISSION_MATRIX.get(role, set())


def get_role_difference(role_a: UserRole, role_b: UserRole) -> Set[Permission]:
    """Get permissions that role_a has but role_b does not."""
    perms_a = PERMISSION_MATRIX.get(role_a, set())
    perms_b = PERMISSION_MATRIX.get(role_b, set())
    return perms_a - perms_b
