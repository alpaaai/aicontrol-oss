"""Tests for cumulative token/cost budget enforcement on /intercept (WS3)."""
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import text

_TEST_AGENT_ID = "00000000-0000-0000-0000-000000000001"


@pytest_asyncio.fixture(loop_scope="session")
async def clean_token_budget_session():
    session_id = uuid.uuid4()
    yield session_id
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM audit_events WHERE session_id = :id"), {"id": str(session_id)})
        await session.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(session_id)})
        await session.commit()


@pytest.mark.asyncio
async def test_intercept_denies_when_cumulative_tokens_exceed_budget(
    client, agent_token, admin_token, clean_token_budget_session
):
    session_id = clean_token_budget_session
    await client.post("/policies", headers=admin_token, json={
        "name": "test_token_budget_intercept",
        "description": "Deny after 100k cumulative tokens on expensive_llm_probe_tool",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["expensive_llm_probe_tool"],
            "token_budget": {"max_tokens": 100000, "window": "session", "on_exceed": "deny"},
        },
        "action": "deny", "severity": "high", "active": True,
    })

    resp1 = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(session_id),
        "agent_id": _TEST_AGENT_ID,
        "agent_name": "claims-processing-agent",
        "tool_name": "expensive_llm_probe_tool",
        "tool_parameters": {},
        "sequence_number": 1,
        "input_tokens": 80000,
        "output_tokens": 0,
    })
    assert resp1.json()["decision"] == "allow"

    resp2 = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(session_id),
        "agent_id": _TEST_AGENT_ID,
        "agent_name": "claims-processing-agent",
        "tool_name": "expensive_llm_probe_tool",
        "tool_parameters": {},
        "sequence_number": 2,
        "input_tokens": 30000,
        "output_tokens": 0,
    })
    assert resp2.json()["decision"] == "allow"

    import asyncio
    from app.models.database import async_session_factory
    for _ in range(20):
        async with async_session_factory() as db_session:
            result = await db_session.execute(
                text("SELECT COUNT(*) FROM audit_events WHERE session_id = :id"), {"id": str(session_id)}
            )
            if result.scalar_one() >= 2:
                break
        await asyncio.sleep(0.05)

    resp3 = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(session_id),
        "agent_id": _TEST_AGENT_ID,
        "agent_name": "claims-processing-agent",
        "tool_name": "expensive_llm_probe_tool",
        "tool_parameters": {},
        "sequence_number": 3,
        "input_tokens": 0,
        "output_tokens": 0,
    })
    assert resp3.json()["decision"] == "deny"
    assert "token_budget_exceeded" in resp3.json()["reason"]


@pytest.mark.asyncio
async def test_intercept_with_null_token_usage_degrades_gracefully(
    client, agent_token, admin_token, clean_token_budget_session
):
    """A tool_denylist + token_budget policy targeting a tool that's called
    with no input_tokens/output_tokens (e.g. an MCP-proxy-only agent, per
    WS2's documented scope boundary) must not crash — cumulative_tokens is
    simply 0/absent, so the policy just doesn't fire."""
    session_id = clean_token_budget_session
    await client.post("/policies", headers=admin_token, json={
        "name": "test_token_budget_null_usage",
        "description": "Budget on a tool that gets called with no token data",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["no_token_data_probe_tool"],
            "token_budget": {"max_tokens": 100, "window": "session", "on_exceed": "deny"},
        },
        "action": "deny", "severity": "high", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(session_id),
        "agent_id": _TEST_AGENT_ID,
        "agent_name": "claims-processing-agent",
        "tool_name": "no_token_data_probe_tool",
        "tool_parameters": {},
        "sequence_number": 1,
    })
    assert resp.status_code == 200
    assert resp.json()["decision"] == "allow"
