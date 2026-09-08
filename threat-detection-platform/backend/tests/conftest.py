"""
Shared test fixtures.

Provides:
- test_client: FastAPI TestClient for API testing
- Settings override for test environment

The test suite runs against the fast, ephemeral in-memory repositories, not
the durable SQL store. We force this by setting USE_DATABASE=false BEFORE any
app module is imported, because routers build their repository instances at
import time. This keeps tests hermetic (no leftover .db file) and preserves
the synchronous .clear() calls the endpoint tests rely on.
"""

import os

os.environ["USE_DATABASE"] = "false"

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async HTTP test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
