"""
Health endpoint tests.

Verifies the development environment is correctly set up
by testing the health check endpoint.
"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint returns 200 with expected fields."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data
    assert "service" in data


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Root endpoint returns service info."""
    response = await client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "service" in data
    assert "docs" in data
    assert data["docs"] == "/docs"
