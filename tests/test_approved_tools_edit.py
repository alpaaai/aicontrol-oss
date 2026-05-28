"""Tests for P1-1a: PATCH /agents/{agent_id}/approved-tools endpoint."""
import uuid
import pytest
import pytest_asyncio
from contextlib import contextmanager
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text


TEST_EDIT_AGENT_ID = uuid.UUID("b1111111-1111-1111-1111-111111111111")


@pytest_asyncio.fixture(scope="session")
async def p1_1a_agent():
    """Insert a test agent for P1-1a PATCH endpoint tests."""
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, 'p1-1a-edit-agent', 'test@test.com', 'active', CAST(:tools AS jsonb))
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": str(TEST_EDIT_AGENT_ID),
            "tools": '["initial_tool"]',
        })
        await session.commit()

    yield TEST_EDIT_AGENT_ID

    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM agents WHERE id = :id"), {"id": str(TEST_EDIT_AGENT_ID)}
        )
        await session.commit()


@contextmanager
def _mock_admin():
    from app.main import app
    from app.core.auth import require_admin
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_a_patch_approved_tools_replaces_list(p1_1a_agent):
    """Valid agent_id + valid list: returns 200 with updated list and DB round-trip confirms write."""
    from app.main import app
    from app.models.database import async_session_factory
    from app.models.schemas import Agent

    agent_id = p1_1a_agent

    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/agents/{agent_id}/approved-tools",
                json={"approved_tools": ["tool_a", "tool_b"]},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == str(agent_id)
    assert data["approved_tools"] == ["tool_a", "tool_b"]

    # DB round-trip: confirm the write actually persisted
    async with async_session_factory() as session:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one()
        assert agent.approved_tools == ["tool_a", "tool_b"]


@pytest.mark.asyncio
async def test_b_patch_approved_tools_clears_to_empty(p1_1a_agent):
    """Valid agent_id + empty list: returns 200 with approved_tools=[], agent becomes unrestricted."""
    from app.main import app

    agent_id = p1_1a_agent

    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/agents/{agent_id}/approved-tools",
                json={"approved_tools": []},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["approved_tools"] == []


@pytest.mark.asyncio
async def test_c_patch_approved_tools_nonexistent_agent_returns_404(p1_1a_agent):
    """Non-existent agent_id returns 404."""
    from app.main import app

    nonexistent_id = uuid.uuid4()

    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/agents/{nonexistent_id}/approved-tools",
                json={"approved_tools": ["some_tool"]},
            )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_d_patch_approved_tools_invalid_body_returns_422(p1_1a_agent):
    """Invalid body (approved_tools is a string, not a list) returns 422."""
    from app.main import app

    agent_id = p1_1a_agent

    with _mock_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/agents/{agent_id}/approved-tools",
                json={"approved_tools": "not_a_list"},
            )

    assert response.status_code == 422
