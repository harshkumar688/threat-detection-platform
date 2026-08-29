"""
Auth API Endpoint Tests (HTTP level)

Verifies the /api/v1/auth/* router is wired to the real AuthService,
not a disconnected placeholder. Confirms security properties are
enforced through actual HTTP requests:
- Account lockout after repeated failed logins
- Audit log entries recorded for real HTTP-triggered events
- Registered users can log in and appear in /me with correct role
- Deactivated-style edge cases behave correctly end-to-end
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.v1.auth import _audit as auth_audit_log, _repo as user_repo
from app.auth.audit import AuditAction
from app.auth.service import MAX_FAILED_ATTEMPTS


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestRealLoginFlow:
    @pytest.mark.asyncio
    async def test_register_then_login_then_me(self, client):
        # Register a real operator account through the HTTP API
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "flow-operator@test.com",
            "password": "SecurePass123",
            "full_name": "Flow Operator",
            "role": "operator",
        })
        assert reg_resp.status_code == 201

        # Log in with the real credentials
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "flow-operator@test.com",
            "password": "SecurePass123",
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # /me reflects the real, persisted user
        me_resp = await client.get("/api/v1/auth/me", headers=auth_header(token))
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["email"] == "flow-operator@test.com"
        assert data["role"] == "operator"
        assert data["full_name"] == "Flow Operator"

    @pytest.mark.asyncio
    async def test_password_never_returned_in_any_response(self, client):
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "secret-check@test.com",
            "password": "SuperSecretPassword1",
            "full_name": "Secret Check",
            "role": "viewer",
        })
        body_text = reg_resp.text
        assert "SuperSecretPassword1" not in body_text
        assert "password_hash" not in body_text


class TestAccountLockoutViaHttp:
    @pytest.mark.asyncio
    async def test_lockout_after_max_failed_logins(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "lockout-http@test.com",
            "password": "CorrectPass123",
            "full_name": "Lockout Test",
            "role": "viewer",
        })

        # Fail login MAX_FAILED_ATTEMPTS times
        for _ in range(MAX_FAILED_ATTEMPTS):
            resp = await client.post("/api/v1/auth/login", json={
                "email": "lockout-http@test.com",
                "password": "WrongPassword",
            })
            assert resp.status_code == 401

        # Next attempt, even with the CORRECT password, must be rejected (locked)
        resp = await client.post("/api/v1/auth/login", json={
            "email": "lockout-http@test.com",
            "password": "CorrectPass123",
        })
        assert resp.status_code == 401
        assert "locked" in resp.json()["error"]["message"].lower()


class TestRefreshTokenViaHttp:
    @pytest.mark.asyncio
    async def test_refresh_issues_new_valid_access_token(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "refresh-http@test.com",
            "password": "RefreshPass123",
            "full_name": "Refresh Test",
            "role": "viewer",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "refresh-http@test.com",
            "password": "RefreshPass123",
        })
        refresh_token = login_resp.json()["refresh_token"]

        refresh_resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert refresh_resp.status_code == 200
        new_access = refresh_resp.json()["access_token"]

        # New access token works against a protected endpoint
        me_resp = await client.get("/api/v1/auth/me", headers=auth_header(new_access))
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "refresh-http@test.com"

    @pytest.mark.asyncio
    async def test_refresh_rejects_access_token(self, client):
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "admin@threatplatform.local",
            "password": "admin123",
        })
        access_token = login_resp.json()["access_token"]

        # Using an access token where a refresh token is expected must fail
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": access_token,
        })
        assert resp.status_code == 401


class TestAuditLoggingViaHttp:
    @pytest.mark.asyncio
    async def test_http_login_success_is_audited(self, client):
        entries_before = auth_audit_log.total_entries

        await client.post("/api/v1/auth/login", json={
            "email": "admin@threatplatform.local",
            "password": "admin123",
        })

        entries = auth_audit_log.get_entries(action=AuditAction.LOGIN_SUCCESS)
        assert len(entries) >= 1
        assert auth_audit_log.total_entries > entries_before

    @pytest.mark.asyncio
    async def test_http_login_failure_is_audited(self, client):
        await client.post("/api/v1/auth/login", json={
            "email": "admin@threatplatform.local",
            "password": "definitely-wrong",
        })

        entries = auth_audit_log.get_entries(action=AuditAction.LOGIN_FAILED)
        assert any(e.user_email == "admin@threatplatform.local" for e in entries)


class TestMeRejectsForgedTokens:
    @pytest.mark.asyncio
    async def test_me_rejects_token_for_nonexistent_user(self, client):
        from app.core.security import create_access_token

        # A syntactically valid JWT, but for a user_id that doesn't exist
        forged_token = create_access_token(
            subject="00000000-0000-0000-0000-000000000000",
            role="admin",
        )
        resp = await client.get("/api/v1/auth/me", headers=auth_header(forged_token))
        assert resp.status_code == 401
