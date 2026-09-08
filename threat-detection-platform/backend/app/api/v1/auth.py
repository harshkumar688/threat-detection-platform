"""
Authentication Router

Endpoints:
- POST /auth/login      → Authenticate and issue tokens
- POST /auth/register   → Create new user account
- POST /auth/refresh    → Refresh access token
- GET  /auth/me         → Get current user profile

Wired to the real AuthService (app/auth), which provides:
- bcrypt password hashing (never plaintext)
- Account lockout after repeated failed attempts
- Audit logging of every auth event
- Role-based JWT issuance
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import CurrentUser, get_current_user
from app.auth import AuthAuditLog, AuthService, InMemoryUserRepository, SqlUserRepository, UserRole
from app.auth.service import (
    AccountDeactivatedError,
    AccountLockedError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
)
from app.core.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

import os as _os
_repo = (
    InMemoryUserRepository()
    if _os.getenv("USE_DATABASE", "true").lower() in ("0", "false", "no")
    else SqlUserRepository()
)
_audit = AuthAuditLog()
_service = AuthService(_repo, _audit)


async def seed_admin_user() -> None:
    """
    Seed the default administrator account. Called by app lifespan AFTER
    init_db() so the database table exists. Idempotent — does nothing if the
    admin user already exists.
    """
    settings = get_settings()
    existing = await _repo.get_by_email(settings.admin_email)
    if existing is None:
        await _service.register(
            email=settings.admin_email,
            password=settings.admin_password,
            full_name=settings.admin_full_name,
            role=UserRole.ADMIN,
        )


def _seed_admin_sync() -> None:
    """
    Sync shim — only used when running without a database (in-memory path,
    tests, or first-boot before lifespan fires). Not called when USE_DATABASE
    is true because lifespan handles seeding there.
    """
    import asyncio
    import os

    if os.getenv("USE_DATABASE", "true").lower() not in ("0", "false", "no"):
        return  # Deferred to lifespan; DB not ready here

    async def _do():
        await seed_admin_user()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_do())
        else:
            loop.run_until_complete(_do())
    except RuntimeError:
        asyncio.run(_do())


_seed_admin_sync()


def _user_to_response(user) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat(),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user",
    description="Validates credentials and returns JWT access + refresh tokens.",
)
async def login(body: LoginRequest, request: Request):
    """
    Authenticate with email and password.

    Returns JWT tokens on success.
    Raises 401 on invalid credentials or deactivated account.
    Raises 423 (via 401 mapping) if account is locked from repeated failures.
    """
    client_ip = request.client.host if request.client else None

    try:
        access_token, refresh_token, expires_in = await _service.login(
            body.email, body.password, ip_address=client_ip
        )
    except AccountLockedError as e:
        raise UnauthorizedError(
            f"Account locked due to repeated failed attempts. Try again after {e.locked_until.isoformat()}."
        )
    except AccountDeactivatedError:
        raise UnauthorizedError("Account is deactivated")
    except InvalidCredentialsError:
        raise UnauthorizedError("Invalid email or password")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Creates a new user account. Email must be unique.",
)
async def register(body: RegisterRequest, request: Request):
    """
    Register a new user account.

    Password is hashed with bcrypt before storage — never kept as plaintext.
    Validates email uniqueness and role validity.
    """
    try:
        role = UserRole(body.role)
    except ValueError:
        raise ValidationError("Invalid role. Must be: admin, operator, viewer", field="role")

    client_ip = request.client.host if request.client else None

    try:
        user = await _service.register(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            role=role,
            ip_address=client_ip,
        )
    except EmailAlreadyExistsError:
        raise ConflictError(f"Email already registered: {body.email}")

    return _user_to_response(user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access token.",
)
async def refresh_token(body: RefreshRequest, request: Request):
    """Refresh an expired access token using a valid refresh token."""
    client_ip = request.client.host if request.client else None

    try:
        access_token, new_refresh, expires_in = await _service.refresh_token(
            body.refresh_token, ip_address=client_ip
        )
    except InvalidCredentialsError:
        raise UnauthorizedError("Invalid or expired refresh token")

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=expires_in,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Returns the profile of the authenticated user.",
)
async def get_me(user: CurrentUser = Depends(get_current_user)):
    """
    Get the currently authenticated user's profile.

    Looks up the real user record by the UUID embedded in the JWT.
    Raises 401 if the token subject does not correspond to an existing user
    (e.g., a forged or stale token for a deleted account).
    """
    try:
        user_uuid = UUID(user.user_id)
    except (ValueError, AttributeError):
        raise UnauthorizedError("Invalid user identity in token")

    user_data = await _service.get_user(user_uuid)
    if user_data is None:
        raise UnauthorizedError("User not found")

    return _user_to_response(user_data)
