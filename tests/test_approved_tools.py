"""Tests for P1-1: per-agent approved_tools enforcement at /intercept."""
import uuid
import pytest
import pytest_asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

AGENT_WITH_TOOLS_ID = uuid.UUID("a1111111-1111-1111-1111-111111111111")
AGENT_EMPTY_TOOLS_ID = uuid.UUID("a2222222-2222-2222-2222-222222222222")


@pytest_asyncio.fixture(scope="session")
async def p1_1_agents():
    """Insert test agents for P1-1 approved_tools tests. Cleaned up after session."""
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES
              (:id1, 'p1-1-restricted-agent', 'test@test.com', 'active', CAST(:tools1 AS jsonb)),
              (:id2, 'p1-1-unrestricted-agent', 'test@test.com', 'active', CAST(:tools2 AS jsonb))
            ON CONFLICT (id) DO NOTHING
        """), {
            "id1": str(AGENT_WITH_TOOLS_ID),
            "tools1": '["query_credit_bureau", "run_risk_model"]',
            "id2": str(AGENT_EMPTY_TOOLS_ID),
            "tools2": '[]',
        })
        await session.commit()

    yield {
        "with_tools_id": AGENT_WITH_TOOLS_ID,
        "empty_tools_id": AGENT_EMPTY_TOOLS_ID,
    }

    async with async_session_factory() as session:
        for agent_id in [AGENT_WITH_TOOLS_ID, AGENT_EMPTY_TOOLS_ID]:
            await session.execute(text(
                "DELETE FROM audit_events WHERE agent_id = :id"
            ), {"id": str(agent_id)})
            await session.execute(text(
                "DELETE FROM sessions WHERE agent_id = :id"
            ), {"id": str(agent_id)})
            await session.execute(text(
                "DELETE FROM agents WHERE id = :id"
            ), {"id": str(agent_id)})
        await session.commit()


@contextmanager
def _mock_auth():
    from app.main import app
    from app.core.auth import require_agent
    app.dependency_overrides[require_agent] = lambda: {"role": "agent"}
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_agent, None)


def _intercept_payload(agent_id: uuid.UUID, tool_name: str) -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "agent_id": str(agent_id),
        "agent_name": "test-agent",
        "tool_name": tool_name,
        "tool_parameters": {},
        "sequence_number": 1,
    }


@pytest.mark.asyncio
async def test_a_tool_in_approved_list_passes_to_opa(p1_1_agents):
    """Tool in approved_tools passes the gate; OPA evaluation runs and decides."""
    from app.main import app

    agent_id = p1_1_agents["with_tools_id"]
    mock_evaluate = AsyncMock(return_value={"decision": "allow", "reason": "default_allow"})

    with patch("app.routers.intercept.evaluate", new=mock_evaluate), \
         patch("app.routers.intercept.write_event", new=AsyncMock(return_value=uuid.uuid4())), \
         patch("app.routers.intercept.get_active_policies", new=AsyncMock(return_value=[])), \
         patch("app.routers.intercept.ensure_session", new=AsyncMock()), \
         _mock_auth():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/intercept",
                json=_intercept_payload(agent_id, "query_credit_bureau"),
            )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "allow"
    assert mock_evaluate.called, "OPA evaluate must be called when tool is in approved_tools"


@pytest.mark.asyncio
async def test_b_tool_not_in_approved_list_denied_before_opa(p1_1_agents):
    """Tool not in approved_tools is denied immediately with tool_not_approved_for_agent; OPA never called."""
    from app.main import app

    agent_id = p1_1_agents["with_tools_id"]
    mock_evaluate = AsyncMock(return_value={"decision": "allow", "reason": "default_allow"})
    captured: dict = {}

    def capture_append(event):
        captured.update(event)
        return uuid.uuid4()

    wal_mock = MagicMock()
    wal_mock.append.side_effect = capture_append

    with patch("app.routers.intercept.evaluate", new=mock_evaluate), \
         patch("app.routers.intercept.wal_writer", new=wal_mock), \
         patch("app.routers.intercept.get_active_policies", new=AsyncMock(return_value=[])), \
         patch("app.routers.intercept.ensure_session", new=AsyncMock()), \
         _mock_auth():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/intercept",
                json=_intercept_payload(agent_id, "bulk_export_records"),
            )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "deny"
    assert data["reason"] == "tool_not_approved_for_agent"
    assert "audit_event_id" in data

    assert not mock_evaluate.called, "OPA must not be called when approved_tools gate denies"

    assert captured.get("decision") == "deny"
    assert captured.get("decision_reason") == "tool_not_approved_for_agent"
    assert captured.get("policy_name") == "approved_tools"
    assert captured.get("policy_id") is None
    assert captured.get("risk_delta") == 25


@pytest.mark.asyncio
async def test_c_agent_not_in_db_passes_through(p1_1_agents):
    """Agent not found in DB (simulates null approved_tools): any tool passes to OPA unchanged."""
    from app.main import app

    nonexistent_agent_id = uuid.uuid4()  # random — not in DB
    mock_evaluate = AsyncMock(return_value={"decision": "allow", "reason": "default_allow"})

    with patch("app.routers.intercept.evaluate", new=mock_evaluate), \
         patch("app.routers.intercept.write_event", new=AsyncMock(return_value=uuid.uuid4())), \
         patch("app.routers.intercept.get_active_policies", new=AsyncMock(return_value=[])), \
         patch("app.routers.intercept.ensure_session", new=AsyncMock()), \
         _mock_auth():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/intercept",
                json=_intercept_payload(nonexistent_agent_id, "any_tool_whatsoever"),
            )

    assert response.status_code == 200
    assert mock_evaluate.called, "OPA must run when agent is not found in DB"
    data = response.json()
    assert data["reason"] != "tool_not_approved_for_agent"


@pytest.mark.asyncio
async def test_d_empty_approved_tools_passes_any_tool(p1_1_agents):
    """Agent with approved_tools=[] is unrestricted; any tool passes to OPA."""
    from app.main import app

    agent_id = p1_1_agents["empty_tools_id"]
    mock_evaluate = AsyncMock(return_value={"decision": "allow", "reason": "default_allow"})

    with patch("app.routers.intercept.evaluate", new=mock_evaluate), \
         patch("app.routers.intercept.write_event", new=AsyncMock(return_value=uuid.uuid4())), \
         patch("app.routers.intercept.get_active_policies", new=AsyncMock(return_value=[])), \
         patch("app.routers.intercept.ensure_session", new=AsyncMock()), \
         _mock_auth():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/intercept",
                json=_intercept_payload(agent_id, "completely_unrestricted_tool"),
            )

    assert response.status_code == 200
    assert mock_evaluate.called, "OPA must run when approved_tools is empty"
    data = response.json()
    assert data["reason"] != "tool_not_approved_for_agent"


@pytest.mark.asyncio
async def test_e_tool_in_list_but_opa_denies_returns_opa_reason(p1_1_agents):
    """Tool in approved_tools passes the gate; if OPA denies, reason is OPA's not tool_not_approved_for_agent."""
    from app.main import app

    agent_id = p1_1_agents["with_tools_id"]

    with patch("app.routers.intercept.evaluate", new=AsyncMock(
        return_value={"decision": "deny", "reason": "tool_denylisted"}
    )), patch("app.routers.intercept.write_event", new=AsyncMock(return_value=uuid.uuid4())), \
         patch("app.routers.intercept.get_active_policies", new=AsyncMock(return_value=[])), \
         patch("app.routers.intercept.ensure_session", new=AsyncMock()), \
         _mock_auth():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/intercept",
                json=_intercept_payload(agent_id, "query_credit_bureau"),
            )

    data = response.json()
    assert data["decision"] == "deny"
    assert data["reason"] == "tool_denylisted"
    assert data["reason"] != "tool_not_approved_for_agent"


@pytest.mark.asyncio
async def test_f_normal_allow_audit_event_does_not_use_approved_tools_policy_name(p1_1_agents):
    """Normal allow for a tool in approved_tools: audit event policy_name is not 'approved_tools'."""
    from app.main import app

    agent_id = p1_1_agents["with_tools_id"]
    captured: dict = {}

    async def capture_write_event(**kwargs):
        captured.update(kwargs)
        return uuid.uuid4()

    with patch("app.routers.intercept.evaluate", new=AsyncMock(
        return_value={"decision": "allow", "reason": "default_allow"}
    )), patch("app.routers.intercept.write_event", new=AsyncMock(side_effect=capture_write_event)), \
         patch("app.routers.intercept.get_active_policies", new=AsyncMock(return_value=[])), \
         patch("app.routers.intercept.ensure_session", new=AsyncMock()), \
         _mock_auth():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/intercept",
                json=_intercept_payload(agent_id, "query_credit_bureau"),
            )

    assert response.status_code == 200
    assert response.json()["decision"] == "allow"
    assert captured.get("policy_name") != "approved_tools", \
        "Normal allow must not pollute audit log with approved_tools policy_name"
