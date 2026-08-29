"""
Users API Endpoint Tests (HTTP level)

Verifies /api/v1/users/* is wired to the real AuthService/UserRepository
shared with the auth router — not a disconnected placeholder that always
returns empty lists or 404s.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _login(client, email, password):
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestListUsers:
    @pytest.mark.asyncio
    async def test_requires_admin(self, client):
        # Register + login as viewer
        await client.post("/api/v1/auth/register", json={
            "email": "viewer-users-test@test.com",
            "password": "ViewerPass123",
            "full_name": "Viewer",
            "role": "viewer",
        })
        token = await _login(client, "viewer-users-test@test.com", "ViewerPass123")

        resp = await client.get("/api/v1/users/", headers=auth_header(token))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_sees_registered_users(self, client):
        # Register a distinguishable user
        await client.post("/api/v1/auth/register", json={
            "email": "listed-user@test.com",
            "password": "ListedPass123",
            "full_name": "Listed User",
            "role": "operator",
        })

        admin_token = await _login(client, "admin@threatplatform.local", "admin123")
        resp = await client.get("/api/v1/users/", headers=auth_header(admin_token))
        assert resp.status_code == 200
        emails = [u["email"] for u in resp.json()]
        assert "listed-user@test.com" in emails


class TestGetUser:
    @pytest.mark.asyncio
    async def test_get_real_user_by_id(self, client):
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "getbyid@test.com",
            "password": "GetByIdPass123",
            "full_name": "Get By Id",
            "role": "viewer",
        })
        user_id = reg_resp.json()["id"]

        admin_token = await _login(client, "admin@threatplatform.local", "admin123")
        resp = await client.get(f"/api/v1/users/{user_id}", headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "getbyid@test.com"

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_404(self, client):
        admin_token = await _login(client, "admin@threatplatform.local", "admin123")
        resp = await client.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000000",
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 404


class TestDeactivateUser:
    @pytest.mark.asyncio
    async def test_deactivate_real_user(self, client):
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "deactivate-me@test.com",
            "password": "DeactivatePass123",
            "full_name": "Deactivate Me",
            "role": "viewer",
        })
        user_id = reg_resp.json()["id"]

        admin_token = await _login(client, "admin@threatplatform.local", "admin123")
        resp = await client.put(
            f"/api/v1/users/{user_id}/deactivate", headers=auth_header(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # Deactivated user can no longer log in
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "deactivate-me@test.com",
            "password": "DeactivatePass123",
        })
        assert login_resp.status_code == 401


class TestChangeUserRole:
    @pytest.mark.asyncio
    async def test_change_role_reflected_in_next_login(self, client):
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "promote-me@test.com",
            "password": "PromotePass123",
            "full_name": "Promote Me",
            "role": "viewer",
        })
        user_id = reg_resp.json()["id"]

        admin_token = await _login(client, "admin@threatplatform.local", "admin123")
        resp = await client.put(
            f"/api/v1/users/{user_id}/role",
            headers=auth_header(admin_token),
            json={"role": "operator"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "operator"

        # New login token reflects the updated role
        new_token = await _login(client, "promote-me@test.com", "PromotePass123")
        me_resp = await client.get("/api/v1/auth/me", headers=auth_header(new_token))
        assert me_resp.json()["role"] == "operator"

    @pytest.mark.asyncio
    async def test_invalid_role_rejected(self, client):
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": "badrole@test.com",
            "password": "BadRolePass123",
            "full_name": "Bad Role",
            "role": "viewer",
        })
        user_id = reg_resp.json()["id"]

        admin_token = await _login(client, "admin@threatplatform.local", "admin123")
        resp = await client.put(
            f"/api/v1/users/{user_id}/role",
            headers=auth_header(admin_token),
            json={"role": "superuser"},
        )
        assert resp.status_code == 422
