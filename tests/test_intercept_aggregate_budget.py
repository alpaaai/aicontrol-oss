"""Tests that an agent-level aggregate budget policy denies a call even
when the specific tool has no per-tool token_budget condition at all --
proving the new standalone "budget" rule_type is reachable end-to-end
through /intercept, not just directly against OPA (WS-F)."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(loop_scope="session")
async def agent_with_high_spend():
    from app.models.database import async_session_factory
    agent_id = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, 'aggregate-budget-test-agent', 'test@test.com', 'active', CAST('[]' AS jsonb))
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(agent_id)})
        await session.execute(text("""
            INSERT INTO sessions (id, agent_id, status) VALUES (:sid, :aid, 'active')
        """), {"sid": str(session_id), "aid": str(agent_id)})
        await session.execute(text("""
            INSERT INTO audit_events (id, session_id, agent_id, agent_name, tool_name, tool_parameters,
                decision, decision_reason, sequence_number, duration_ms, cost_usd, bypass, enforced)
            VALUES (:eid, :sid, :aid, 'aggregate-budget-test-agent', 'unrelated_tool_1', CAST('{}' AS jsonb),
                'allow', 'default_allow', 1, 5, 150.0, false, true)
        """), {"eid": str(uuid.uuid4()), "sid": str(session_id), "aid": str(agent_id)})
        await session.commit()
    yield agent_id, session_id
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM audit_events WHERE agent_id = :id"), {"id": str(agent_id)})
        await session.execute(text("DELETE FROM sessions WHERE agent_id = :id"), {"id": str(agent_id)})
        await session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": str(agent_id)})
        await session.commit()


@pytest.mark.asyncio
async def test_agent_level_budget_denies_across_different_tools(client, agent_token, admin_token, agent_with_high_spend):
    """Prior spend (seeded at $150, exceeding the $100 cap) alone triggers
    the deny -- the budget check runs against cumulative spend so far,
    before this call's own cost is added, matching the existing per-tool
    build_token_budgets' semantics."""
    agent_id, session_id = agent_with_high_spend
    await client.post("/policies", headers=admin_token, json={
        "name": "test_aggregate_agent_budget",
        "description": "Deny once this agent's total spend crosses $100, any tool",
        "rule_type": "budget",
        "condition": {"scope": "agent", "max_cost_usd": 100, "window": "session", "on_exceed": "deny"},
        "action": "deny", "severity": "high", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": "aggregate-budget-test-agent", "tool_name": "a_completely_different_tool_2",
        "tool_parameters": {}, "sequence_number": 2,
    })
    assert resp.status_code == 200
    assert resp.json()["decision"] == "deny"
    assert "budget_exceeded" in resp.json()["reason"]
