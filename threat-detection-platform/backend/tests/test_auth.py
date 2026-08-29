"""
Authentication & Authorization Tests

Tests:
- Password hashing (never plaintext)
- Login success/failure
- Account lockout
- Token creation and validation
- Token refresh
- Role-based permissions
- Permission matrix completeness
- Audit logging
- Deactivation
"""

import pytest
from uuid import uuid4

from app.auth import (
    AuthService,
    AuthAuditLog,
    AuditAction,
    InMemoryUserRepository,
    User,
    UserRole,
    Permission,
    has_permission,
    PERMISSION_MATRIX,
)
from app.auth.service import (
    InvalidCredentialsError,
    AccountLockedError,
    AccountDeactivatedError,
    EmailAlreadyExistsError,
    MAX_FAILED_ATTEMPTS,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def repo():
    return InMemoryUserRepository()


@pytest.fixture
def audit():
    return AuthAuditLog()


@pytest.fixture
def service(repo, audit):
    return AuthService(repo, audit)


# =============================================================================
# Password Hashing Tests
# =============================================================================

class TestPasswordHashing:
    """Verify passwords are NEVER stored as plaintext."""

    def test_hash_password_not_plaintext(self):
        hashed = hash_password("MySecurePass123")
        assert hashed != "MySecurePass123"
        assert len(hashed) > 50  # bcrypt hashes are 60 chars

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = hash_password("test")
        assert hashed.startswith("$2")  # bcrypt prefix

    def test_verify_correct_password(self):
        hashed = hash_password("CorrectPassword")
        assert verify_password("CorrectPassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("CorrectPassword")
        assert verify_password("WrongPassword", hashed) is False

    def test_different_passwords_different_hashes(self):
        h1 = hash_password("password1")
        h2 = hash_password("password2")
        assert h1 != h2

    def test_same_password_different_hashes(self):
        """bcrypt uses random salt — same input produces different hash."""
        h1 = hash_password("SamePassword")
        h2 = hash_password("SamePassword")
        assert h1 != h2  # Different salts
        # But both verify correctly
        assert verify_password("SamePassword", h1) is True
        assert verify_password("SamePassword", h2) is True

    def test_empty_password_verifies_false(self):
        hashed = hash_password("real_password")
        assert verify_password("", hashed) is False


# =============================================================================
# Token Tests
# =============================================================================

class TestTokens:
    """Tests for JWT token creation and validation."""

    def test_create_access_token(self):
        token = create_access_token("user-123", role="operator")
        assert isinstance(token, str)
        assert len(token) > 50

    def test_decode_valid_token(self):
        token = create_access_token("user-123", role="admin", extra_claims={"email": "a@b.com"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert payload["email"] == "a@b.com"

    def test_decode_invalid_token(self):
        payload = decode_token("not.a.valid.token")
        assert payload is None

    def test_decode_tampered_token(self):
        token = create_access_token("user-123", role="admin")
        # Tamper with it
        tampered = token[:-5] + "XXXXX"
        payload = decode_token(tampered)
        assert payload is None

    def test_refresh_token_type(self):
        token = create_refresh_token("user-123")
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-123"

    def test_access_token_has_role(self):
        token = create_access_token("u1", role="viewer")
        payload = decode_token(token)
        assert payload["role"] == "viewer"


# =============================================================================
# Registration Tests
# =============================================================================

class TestRegistration:
    """Tests for user registration."""

    @pytest.mark.asyncio
    async def test_register_success(self, service):
        user = await service.register("new@test.com", "SecurePass123", "New User")
        assert user.email == "new@test.com"
        assert user.full_name == "New User"
        assert user.role == UserRole.VIEWER
        assert user.is_active is True
        # Password must be hashed, NOT plaintext
        assert user.password_hash != "SecurePass123"
        assert user.password_hash.startswith("$2")

    @pytest.mark.asyncio
    async def test_register_with_role(self, service):
        user = await service.register("op@test.com", "Pass12345", "Operator", UserRole.OPERATOR)
        assert user.role == UserRole.OPERATOR

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, service):
        await service.register("dup@test.com", "Pass12345", "First")
        with pytest.raises(EmailAlreadyExistsError):
            await service.register("dup@test.com", "Pass12345", "Second")

    @pytest.mark.asyncio
    async def test_register_email_case_insensitive(self, service):
        await service.register("User@Test.COM", "Pass12345", "User")
        with pytest.raises(EmailAlreadyExistsError):
            await service.register("user@test.com", "Pass12345", "User2")

    @pytest.mark.asyncio
    async def test_register_creates_audit_entry(self, service, audit):
        await service.register("audit@test.com", "Pass12345", "Audit User")
        entries = audit.get_entries(action=AuditAction.REGISTER)
        assert len(entries) == 1
        assert entries[0].user_email == "audit@test.com"


# =============================================================================
# Login Tests
# =============================================================================

class TestLogin:
    """Tests for authentication."""

    @pytest.mark.asyncio
    async def test_login_success(self, service):
        await service.register("login@test.com", "Pass12345", "Login User")
        access, refresh, expires = await service.login("login@test.com", "Pass12345")

        assert len(access) > 50
        assert len(refresh) > 50
        assert expires > 0

        # Verify token content
        payload = decode_token(access)
        assert payload["role"] == "viewer"
        assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, service):
        await service.register("user@test.com", "CorrectPass", "User")
        with pytest.raises(InvalidCredentialsError):
            await service.login("user@test.com", "WrongPass")

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, service):
        with pytest.raises(InvalidCredentialsError):
            await service.login("nobody@test.com", "anything")

    @pytest.mark.asyncio
    async def test_login_deactivated_account(self, service, repo):
        user = await service.register("deact@test.com", "Pass12345", "Deact")
        user.is_active = False
        await repo.update(user)

        with pytest.raises(AccountDeactivatedError):
            await service.login("deact@test.com", "Pass12345")

    @pytest.mark.asyncio
    async def test_login_updates_last_login(self, service, repo):
        user = await service.register("time@test.com", "Pass12345", "Time User")
        assert user.last_login_at is None

        await service.login("time@test.com", "Pass12345")
        updated = await repo.get_by_email("time@test.com")
        assert updated.last_login_at is not None

    @pytest.mark.asyncio
    async def test_login_success_resets_failed_count(self, service, repo):
        await service.register("reset@test.com", "Pass12345", "Reset User")

        # Fail a few times
        for _ in range(3):
            with pytest.raises(InvalidCredentialsError):
                await service.login("reset@test.com", "wrong")

        user = await repo.get_by_email("reset@test.com")
        assert user.failed_login_count == 3

        # Successful login resets
        await service.login("reset@test.com", "Pass12345")
        user = await repo.get_by_email("reset@test.com")
        assert user.failed_login_count == 0


# =============================================================================
# Account Lockout Tests
# =============================================================================

class TestAccountLockout:
    """Tests for brute-force protection."""

    @pytest.mark.asyncio
    async def test_lockout_after_max_attempts(self, service):
        await service.register("lock@test.com", "Pass12345", "Lock User")

        for _ in range(MAX_FAILED_ATTEMPTS):
            with pytest.raises(InvalidCredentialsError):
                await service.login("lock@test.com", "wrong")

        # Next attempt should be locked
        with pytest.raises(AccountLockedError):
            await service.login("lock@test.com", "Pass12345")

    @pytest.mark.asyncio
    async def test_lockout_audit_logged(self, service, audit):
        await service.register("lockaudit@test.com", "Pass12345", "Lock Audit")

        for _ in range(MAX_FAILED_ATTEMPTS):
            with pytest.raises(InvalidCredentialsError):
                await service.login("lockaudit@test.com", "wrong")

        locked_entries = audit.get_entries(action=AuditAction.ACCOUNT_LOCKED)
        assert len(locked_entries) == 1


# =============================================================================
# Token Refresh Tests
# =============================================================================

class TestTokenRefresh:
    """Tests for token refresh flow."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, service):
        await service.register("refresh@test.com", "Pass12345", "Refresh")
        _, refresh, _ = await service.login("refresh@test.com", "Pass12345")

        new_access, new_refresh, expires = await service.refresh_token(refresh)
        assert len(new_access) > 50
        assert len(new_refresh) > 50

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self, service):
        await service.register("ref2@test.com", "Pass12345", "Ref2")
        access, _, _ = await service.login("ref2@test.com", "Pass12345")

        # Using access token as refresh should fail
        with pytest.raises(InvalidCredentialsError):
            await service.refresh_token(access)

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token_fails(self, service):
        with pytest.raises(InvalidCredentialsError):
            await service.refresh_token("invalid.token.here")


# =============================================================================
# Permission Matrix Tests
# =============================================================================

class TestPermissions:
    """Tests for the role-based permission matrix."""

    def test_admin_has_all_permissions(self):
        for perm in Permission:
            assert has_permission(UserRole.ADMIN, perm) is True

    def test_viewer_cannot_manage_users(self):
        assert has_permission(UserRole.VIEWER, Permission.MANAGE_USERS) is False

    def test_viewer_cannot_manage_cameras(self):
        assert has_permission(UserRole.VIEWER, Permission.MANAGE_CAMERAS) is False

    def test_viewer_cannot_create_incidents(self):
        assert has_permission(UserRole.VIEWER, Permission.CREATE_INCIDENTS) is False

    def test_viewer_cannot_acknowledge_alerts(self):
        assert has_permission(UserRole.VIEWER, Permission.ACKNOWLEDGE_ALERTS) is False

    def test_viewer_can_view(self):
        assert has_permission(UserRole.VIEWER, Permission.VIEW_INCIDENTS) is True
        assert has_permission(UserRole.VIEWER, Permission.VIEW_ALERTS) is True
        assert has_permission(UserRole.VIEWER, Permission.VIEW_EVIDENCE) is True
        assert has_permission(UserRole.VIEWER, Permission.VIEW_ANALYTICS) is True
        assert has_permission(UserRole.VIEWER, Permission.VIEW_CAMERAS) is True
        assert has_permission(UserRole.VIEWER, Permission.VIEW_LIVE_FEED) is True

    def test_operator_can_manage_incidents(self):
        assert has_permission(UserRole.OPERATOR, Permission.CREATE_INCIDENTS) is True
        assert has_permission(UserRole.OPERATOR, Permission.UPDATE_INCIDENTS) is True
        assert has_permission(UserRole.OPERATOR, Permission.ACKNOWLEDGE_ALERTS) is True

    def test_operator_cannot_manage_users(self):
        assert has_permission(UserRole.OPERATOR, Permission.MANAGE_USERS) is False

    def test_operator_cannot_manage_config(self):
        assert has_permission(UserRole.OPERATOR, Permission.MANAGE_CONFIG) is False

    def test_operator_cannot_delete_evidence(self):
        assert has_permission(UserRole.OPERATOR, Permission.DELETE_EVIDENCE) is False

    def test_operator_can_control_streams(self):
        assert has_permission(UserRole.OPERATOR, Permission.CONTROL_STREAMS) is True

    def test_all_roles_defined(self):
        """Every role must be present in the matrix."""
        for role in UserRole:
            assert role in PERMISSION_MATRIX

    def test_admin_is_superset_of_operator(self):
        admin_perms = PERMISSION_MATRIX[UserRole.ADMIN]
        op_perms = PERMISSION_MATRIX[UserRole.OPERATOR]
        assert op_perms.issubset(admin_perms)

    def test_operator_is_superset_of_viewer(self):
        op_perms = PERMISSION_MATRIX[UserRole.OPERATOR]
        viewer_perms = PERMISSION_MATRIX[UserRole.VIEWER]
        assert viewer_perms.issubset(op_perms)


# =============================================================================
# Audit Log Tests
# =============================================================================

class TestAuditLog:
    """Tests for authentication audit logging."""

    @pytest.mark.asyncio
    async def test_login_success_audited(self, service, audit):
        await service.register("auditlogin@test.com", "Pass12345", "Audit")
        await service.login("auditlogin@test.com", "Pass12345")

        entries = audit.get_entries(action=AuditAction.LOGIN_SUCCESS)
        assert len(entries) >= 1
        assert entries[0].user_email == "auditlogin@test.com"

    @pytest.mark.asyncio
    async def test_login_failure_audited(self, service, audit):
        await service.register("failaudit@test.com", "Pass12345", "Fail")

        with pytest.raises(InvalidCredentialsError):
            await service.login("failaudit@test.com", "wrong")

        entries = audit.get_entries(action=AuditAction.LOGIN_FAILED)
        assert len(entries) >= 1

    @pytest.mark.asyncio
    async def test_failed_login_counter(self, audit):
        audit.log(AuditAction.LOGIN_FAILED, user_email="count@test.com")
        audit.log(AuditAction.LOGIN_FAILED, user_email="count@test.com")
        audit.log(AuditAction.LOGIN_FAILED, user_email="other@test.com")

        count = audit.get_failed_logins("count@test.com", since_minutes=60)
        assert count == 2

    @pytest.mark.asyncio
    async def test_password_change_audited(self, service, audit):
        user = await service.register("pwchange@test.com", "OldPass123", "PW")
        await service.change_password(user.id, "OldPass123", "NewPass456")

        entries = audit.get_entries(action=AuditAction.PASSWORD_CHANGED)
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_deactivation_audited(self, service, audit):
        user = await service.register("deact2@test.com", "Pass12345", "Deact")
        await service.deactivate_user(user.id, by_admin_id="admin-001")

        entries = audit.get_entries(action=AuditAction.ACCOUNT_DEACTIVATED)
        assert len(entries) == 1
        assert "admin-001" in entries[0].details


# =============================================================================
# Password Change Tests
# =============================================================================

class TestPasswordChange:
    """Tests for password change operations."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, service):
        user = await service.register("change@test.com", "OldPass123", "Change")

        await service.change_password(user.id, "OldPass123", "NewPass456")

        # Old password no longer works
        with pytest.raises(InvalidCredentialsError):
            await service.login("change@test.com", "OldPass123")

        # New password works
        access, _, _ = await service.login("change@test.com", "NewPass456")
        assert len(access) > 50

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, service):
        user = await service.register("wrongcurr@test.com", "RealPass123", "WrongCurr")

        with pytest.raises(InvalidCredentialsError):
            await service.change_password(user.id, "WrongCurrent", "NewPass")


# =============================================================================
# Role Change Tests
# =============================================================================

class TestRoleChange:
    """Tests for role management."""

    @pytest.mark.asyncio
    async def test_change_role(self, service, repo):
        user = await service.register("rolechange@test.com", "Pass12345", "RoleChange")
        assert user.role == UserRole.VIEWER

        updated = await service.change_role(user.id, UserRole.OPERATOR, by_admin_id="admin")
        assert updated.role == UserRole.OPERATOR

        # Login should now return operator role in token
        access, _, _ = await service.login("rolechange@test.com", "Pass12345")
        payload = decode_token(access)
        assert payload["role"] == "operator"
