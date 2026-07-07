"""Tests for POST /agents/register — zero-friction SDK self-registration."""
import uuid
import pytest
from contextlib import contextmanager
from httpx import AsyncClient, ASGITransport


@contextmanager
def _auth(role: str = "agent"):
    from app.main import app
    from app.core.auth import _get_verified_token
    app.dependency_overrides[_get_verified_token] = lambda: {"role": role}
    try:
        yield app
    finally:
        app.dependency_overrides.pop(_get_verified_token, None)


@pytest.mark.asyncio
async def test_register_agent_requires_agent_or_admin_role():
    """POST /agents/register without agent/admin role must return 403."""
    with _auth(role="readonly") as app:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/agents/register",
                json={"name": f"test-agent-{uuid.uuid4().hex[:6]}"},
            )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_register_agent_creates_new_agent():
    """POST /agents/register with a new name must create the agent and return 201."""
    name = f"test-agent-{uuid.uuid4().hex[:6]}"
    with _auth(role="agent") as app:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agents/register", json={"name": name})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == name
    assert "id" in data


@pytest.mark.asyncio
async def test_register_agent_idempotent_same_name_returns_same_id():
    """Calling POST /agents/register twice with the same name must return the same agent_id."""
    name = f"test-agent-{uuid.uuid4().hex[:6]}"
    with _auth(role="agent") as app:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.post("/agents/register", json={"name": name})
            second = await client.post("/agents/register", json={"name": name})

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_register_agent_defaults_framework_and_tools():
    """POST /agents/register without framework/approved_tools must default sensibly."""
    name = f"test-agent-{uuid.uuid4().hex[:6]}"
    with _auth(role="agent") as app:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agents/register", json={"name": name})

    data = response.json()
    assert data["framework"] is None
    assert data["approved_tools"] == []


@pytest.mark.asyncio
async def test_register_agent_allows_admin_role_too():
    """POST /agents/register must also work for admin-role tokens, not just agent-role."""
    name = f"test-agent-{uuid.uuid4().hex[:6]}"
    with _auth(role="admin") as app:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agents/register", json={"name": name})
    assert response.status_code == 201
