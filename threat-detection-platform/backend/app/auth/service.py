"""
Authentication Service

Business logic for:
- User registration (with password hashing)
- Login (credential verification + token issuance)
- Token refresh
- Account lockout after repeated failures
- Role management
- Password changes

Security rules enforced here:
- Passwords ALWAYS hashed with bcrypt before storage
- Failed logins tracked and lockout applied
- Tokens validated for type (access vs refresh)
- Deactivated accounts cannot authenticate
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

from .audit import AuditAction, AuthAuditLog
from .models import User, UserRole
from .repository import UserRepository

logger = logging.getLogger(__name__)

# Security constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AuthError(Exception):
    """Base auth error."""
    pass


class InvalidCredentialsError(AuthError):
    pass


class AccountLockedError(AuthError):
    def __init__(self, locked_until: datetime):
        self.locked_until = locked_until
        super().__init__(f"Account locked until {locked_until.isoformat()}")


class AccountDeactivatedError(AuthError):
    pass


class EmailAlreadyExistsError(AuthError):
    pass


class AuthService:
    """
    Authentication and user management service.

    Usage:
        repo = InMemoryUserRepository()
        audit = AuthAuditLog()
        service = AuthService(repo, audit)

        # Register
        user = await service.register("user@email.com", "SecurePass123", "John", UserRole.OPERATOR)

        # Login
        tokens = await service.login("user@email.com", "SecurePass123")

        # Refresh
        tokens = await service.refresh_token(refresh_token_str)
    """

    def __init__(self, repository: UserRepository, audit_log: AuthAuditLog):
        self._repo = repository
        self._audit = audit_log

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        role: UserRole = UserRole.VIEWER,
        ip_address: Optional[str] = None,
    ) -> User:
        """
        Register a new user.

        Password is hashed with bcrypt before storage.
        Email uniqueness is enforced.

        Raises:
            EmailAlreadyExistsError: If email already registered.
        """
        # Check email uniqueness
        existing = await self._repo.get_by_email(email)
        if existing is not None:
            raise EmailAlreadyExistsError(f"Email already registered: {email}")

        # Hash password — NEVER store plaintext
        password_hash = hash_password(password)

        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            full_name=full_name.strip(),
            role=role,
            password_changed_at=datetime.now(timezone.utc),
        )

        user = await self._repo.create(user)

        self._audit.log(
            action=AuditAction.REGISTER,
            user_id=str(user.id),
            user_email=user.email,
            ip_address=ip_address,
            details=f"Registered as {role.value}",
        )

        logger.info(f"User registered: {user.email} (role={role.value})")
        return user

    async def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
    ) -> Tuple[str, str, int]:
        """
        Authenticate user and issue tokens.

        Returns:
            Tuple of (access_token, refresh_token, expires_in_seconds)

        Raises:
            InvalidCredentialsError: Wrong email/password.
            AccountLockedError: Too many failed attempts.
            AccountDeactivatedError: Account is deactivated.
        """
        user = await self._repo.get_by_email(email.lower().strip())

        if user is None:
            self._audit.log(
                action=AuditAction.LOGIN_FAILED,
                user_email=email,
                ip_address=ip_address,
                details="User not found",
            )
            raise InvalidCredentialsError()

        # Check lockout
        if user.is_locked:
            self._audit.log(
                action=AuditAction.LOGIN_LOCKED,
                user_id=str(user.id),
                user_email=user.email,
                ip_address=ip_address,
                details=f"Locked until {user.locked_until.isoformat()}",
            )
            raise AccountLockedError(user.locked_until)

        # Check active
        if not user.is_active:
            self._audit.log(
                action=AuditAction.LOGIN_FAILED,
                user_id=str(user.id),
                user_email=user.email,
                ip_address=ip_address,
                details="Account deactivated",
            )
            raise AccountDeactivatedError()

        # Verify password
        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1

            # Lock account if too many failures
            if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )
                self._audit.log(
                    action=AuditAction.ACCOUNT_LOCKED,
                    user_id=str(user.id),
                    user_email=user.email,
                    ip_address=ip_address,
                    details=f"Locked after {MAX_FAILED_ATTEMPTS} failed attempts",
                )

            await self._repo.update(user)

            self._audit.log(
                action=AuditAction.LOGIN_FAILED,
                user_id=str(user.id),
                user_email=user.email,
                ip_address=ip_address,
                details=f"Wrong password (attempt {user.failed_login_count})",
            )
            raise InvalidCredentialsError()

        # Success — reset failure counter
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        await self._repo.update(user)

        # Issue tokens
        settings = get_settings()
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            extra_claims={"email": user.email},
        )
        refresh_token = create_refresh_token(subject=str(user.id))
        expires_in = settings.jwt_access_token_expire_minutes * 60

        self._audit.log(
            action=AuditAction.LOGIN_SUCCESS,
            user_id=str(user.id),
            user_email=user.email,
            ip_address=ip_address,
        )

        return access_token, refresh_token, expires_in

    async def refresh_token(
        self,
        refresh_token_str: str,
        ip_address: Optional[str] = None,
    ) -> Tuple[str, str, int]:
        """
        Exchange a refresh token for new access + refresh tokens.

        Validates token type and user existence.

        Raises:
            InvalidCredentialsError: If token is invalid or user not found.
        """
        payload = decode_token(refresh_token_str)
        if payload is None or payload.get("type") != "refresh":
            raise InvalidCredentialsError()

        user_id = payload.get("sub")
        user = await self._repo.get_by_id(UUID(user_id))
        if user is None or not user.is_active:
            raise InvalidCredentialsError()

        settings = get_settings()
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            extra_claims={"email": user.email},
        )
        new_refresh = create_refresh_token(subject=str(user.id))
        expires_in = settings.jwt_access_token_expire_minutes * 60

        self._audit.log(
            action=AuditAction.TOKEN_REFRESH,
            user_id=str(user.id),
            user_email=user.email,
            ip_address=ip_address,
        )

        return access_token, new_refresh, expires_in

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Change a user's password.

        Verifies current password before allowing change.

        Raises:
            InvalidCredentialsError: If current password is wrong.
        """
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError()

        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError()

        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        await self._repo.update(user)

        self._audit.log(
            action=AuditAction.PASSWORD_CHANGED,
            user_id=str(user.id),
            user_email=user.email,
            ip_address=ip_address,
        )

    async def deactivate_user(
        self,
        user_id: UUID,
        by_admin_id: str,
        ip_address: Optional[str] = None,
    ) -> User:
        """Deactivate a user account. Admin action."""
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError()

        user.is_active = False
        await self._repo.update(user)

        self._audit.log(
            action=AuditAction.ACCOUNT_DEACTIVATED,
            user_id=str(user.id),
            user_email=user.email,
            ip_address=ip_address,
            details=f"Deactivated by {by_admin_id}",
        )

        return user

    async def change_role(
        self,
        user_id: UUID,
        new_role: UserRole,
        by_admin_id: str,
        ip_address: Optional[str] = None,
    ) -> User:
        """Change a user's role. Admin action."""
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError()

        old_role = user.role
        user.role = new_role
        await self._repo.update(user)

        self._audit.log(
            action=AuditAction.ROLE_CHANGED,
            user_id=str(user.id),
            user_email=user.email,
            ip_address=ip_address,
            details=f"Role changed: {old_role.value} → {new_role.value} (by {by_admin_id})",
        )

        return user

    async def get_user(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        return await self._repo.get_by_id(user_id)

    async def list_users(self, active_only: bool = True) -> list:
        """List all users."""
        return await self._repo.list_all(is_active=active_only if active_only else None)
