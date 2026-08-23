"""Adapter coverage handshake.

Deviation from the plan: `agent_token` is a header dict carrying an *unscoped*
agent token, so the scope-enforcement case mints its own agent-scoped token
rather than reading an `agent_id` off the fixture. Assertions are unchanged.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.models.schemas import Agent


@pytest_asyncio.fixture(loop_scope="session")
async def registered_agent():
    """A real agent row, committed so the live API can see it."""
    from app.models.database import async_session_factory

    agent_id = uuid.uuid4()
    # agents.name is unique, so each test gets its own row rather than sharing
    # one and racing the others.
    name = f"test-agent-coverage-{agent_id.hex[:8]}"
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, :name, 'tests', 'active', '[]')
        """), {"id": agent_id, "name": name})
        await session.commit()
    return agent_id


@pytest_asyncio.fixture(loop_scope="session")
async def scoped_agent_token(registered_agent):
    """An agent token bound to registered_agent, as onboard_agent.py issues."""
    from app.core.auth import create_token, hash_token
    from app.models.database import async_session_factory

    token = create_token(role="agent", description="pytest-agent-fixture")
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO api_tokens (id, token_hash, role, description, revoked, agent_id)
            VALUES (gen_random_uuid(), :hash, 'agent', 'pytest-agent-fixture', false, :agent_id)
        """), {"hash": hash_token(token), "agent_id": registered_agent})
        await session.commit()
    return {"Authorization": f"Bearer {token}"}


async def _load(agent_id):
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        return (await session.execute(
            select(Agent).where(Agent.id == agent_id)
        )).scalar_one()


@pytest.mark.asyncio
async def test_handshake_records_framework_and_hook(client, agent_token, registered_agent):
    resp = await client.post(
        f"/agents/{registered_agent}/coverage",
        headers=agent_token,
        json={
            "framework": "openai_agents_sdk",
            "hook": "RunHooks.on_tool_start",
            "sdk_version": "0.2.3",
            "workflow": "claims_intake",
            "silent_noop_warnings": [],
        },
    )
    assert resp.status_code == 200, resp.text

    agent = await _load(registered_agent)
    assert agent.framework == "openai_agents_sdk"
    assert agent.hook == "RunHooks.on_tool_start"
    assert agent.sdk_version == "0.2.3"
    assert agent.workflow == "claims_intake"
    assert agent.coverage_last_seen_at is not None


@pytest.mark.asyncio
async def test_handshake_stores_silent_noop_warnings(client, agent_token, registered_agent):
    resp = await client.post(
        f"/agents/{registered_agent}/coverage",
        headers=agent_token,
        json={
            "framework": "langgraph", "hook": "BaseCallbackHandler.on_tool_start",
            "sdk_version": "0.4.1", "workflow": "unassigned",
            "silent_noop_warnings": ["sync_tool_denial_swallowed:refund_payment"],
        },
    )
    assert resp.status_code == 200, resp.text

    agent = await _load(registered_agent)
    assert agent.silent_noop_warnings == ["sync_tool_denial_swallowed:refund_payment"]


@pytest.mark.asyncio
async def test_agent_scoped_token_cannot_handshake_for_another_agent(
    client, scoped_agent_token
):
    other = uuid.uuid4()
    resp = await client.post(
        f"/agents/{other}/coverage",
        headers=scoped_agent_token,
        json={"framework": "crewai", "hook": "x", "sdk_version": "1",
              "workflow": "unassigned", "silent_noop_warnings": []},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unknown_agent_auto_registers_in_observe_mode(client, admin_token):
    """D14: a live ungoverned agent must become visible, not 404. It lands in
    observe so auto-registration can never start enforcing against an agent
    nobody configured."""
    new_id = uuid.uuid4()
    resp = await client.post(
        f"/agents/{new_id}/coverage",
        headers=admin_token,
        json={
            "framework": "openai_agents_sdk", "hook": "RunHooks.on_tool_start",
            "sdk_version": "0.2.3", "workflow": "test_autoreg",
            "agent_name": "test-agent-autoregistered",
            "silent_noop_warnings": [],
        },
    )
    assert resp.status_code == 200, resp.text

    agent = await _load(new_id)
    assert agent.name == "test-agent-autoregistered"
    assert agent.governance_mode == "observe"
    assert agent.framework == "openai_agents_sdk"


@pytest.mark.asyncio
async def test_auto_registration_does_not_overwrite_an_existing_agents_mode(
    client, agent_token, registered_agent
):
    """An agent already in govern stays in govern when it handshakes."""
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE agents SET governance_mode = 'govern' WHERE id = :id"),
            {"id": registered_agent},
        )
        await session.commit()

    resp = await client.post(
        f"/agents/{registered_agent}/coverage",
        headers=agent_token,
        json={"framework": "crewai", "hook": "x", "sdk_version": "1",
              "workflow": "unassigned", "silent_noop_warnings": []},
    )
    assert resp.status_code == 200, resp.text

    agent = await _load(registered_agent)
    assert agent.governance_mode == "govern"


@pytest.mark.asyncio
async def test_handshake_returns_the_agent_and_a_coverage_state(
    client, agent_token, registered_agent
):
    resp = await client.post(
        f"/agents/{registered_agent}/coverage",
        headers=agent_token,
        json={"framework": "crewai", "hook": "before_tool_call", "sdk_version": "1",
              "workflow": "unassigned", "silent_noop_warnings": []},
    )
    body = resp.json()
    assert body["agent_id"] == str(registered_agent)
    assert body["coverage_state"] == "governed"
