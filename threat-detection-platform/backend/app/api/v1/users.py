"""
Users Router

Endpoints:
- GET  /users/                → List users (admin)
- GET  /users/{id}            → Get user details (admin)
- PUT  /users/{id}/deactivate  → Deactivate user (admin)
- PUT  /users/{id}/role        → Change user role (admin)

Wired to the same AuthService/UserRepository instances used by the
auth router, so users created via /auth/register are visible here.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_admin
from app.api.v1.auth import _service as auth_service, _user_to_response
from app.auth import UserRole
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


class RoleChangeRequest(BaseModel):
    role: str = Field(description="New role: admin, operator, viewer")


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List users",
    description="List all active system users. Requires admin role.",
)
async def list_users(
    include_inactive: bool = False,
    admin: CurrentUser = Depends(require_admin),
):
    """List all users. Admin only."""
    users = await auth_service.list_users(active_only=not include_inactive)
    return [_user_to_response(u) for u in users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user details",
    description="Get detailed user profile. Requires admin role.",
)
async def get_user(user_id: str, admin: CurrentUser = Depends(require_admin)):
    """Get a user by ID. Admin only."""
    try:
        uuid_val = UUID(user_id)
    except ValueError:
        raise NotFoundError("User", user_id)

    user = await auth_service.get_user(uuid_val)
    if user is None:
        raise NotFoundError("User", user_id)

    return _user_to_response(user)


@router.put(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate user",
    description="Deactivate a user account. Requires admin role.",
)
async def deactivate_user(user_id: str, admin: CurrentUser = Depends(require_admin)):
    """Deactivate a user account. Admin only."""
    try:
        uuid_val = UUID(user_id)
    except ValueError:
        raise NotFoundError("User", user_id)

    existing = await auth_service.get_user(uuid_val)
    if existing is None:
        raise NotFoundError("User", user_id)

    updated = await auth_service.deactivate_user(uuid_val, by_admin_id=admin.user_id)
    return _user_to_response(updated)


@router.put(
    "/{user_id}/role",
    response_model=UserResponse,
    summary="Change user role",
    description="Change a user's role. Requires admin role.",
)
async def change_user_role(
    user_id: str,
    body: RoleChangeRequest,
    admin: CurrentUser = Depends(require_admin),
):
    """Change a user's role. Admin only."""
    try:
        uuid_val = UUID(user_id)
    except ValueError:
        raise NotFoundError("User", user_id)

    try:
        new_role = UserRole(body.role)
    except ValueError:
        raise ValidationError("Invalid role. Must be: admin, operator, viewer", field="role")

    existing = await auth_service.get_user(uuid_val)
    if existing is None:
        raise NotFoundError("User", user_id)

    updated = await auth_service.change_role(uuid_val, new_role, by_admin_id=admin.user_id)
    return _user_to_response(updated)
