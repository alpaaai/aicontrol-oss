"""Tests that /intercept writes through the WAL, and that governance_mode /
bypass are reflected correctly in the eventual audit_events row (WS0)."""
import asyncio
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(loop_scope="session")
async def observe_mode_agent():
    from app.models.database import async_session_factory
    agent_id = uuid.UUID("f1111111-1111-1111-1111-111111111111")
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools, governance_mode)
            VALUES (:id, 'test-agent-observe-intercept', 'test@test.com', 'active', '[]', 'observe')
            ON CONFLICT (id) DO UPDATE SET governance_mode = 'observe'
        """), {"id": str(agent_id)})
        await session.commit()
    yield agent_id
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM audit_events WHERE agent_id = :id"), {"id": str(agent_id)})
        await session.execute(text("DELETE FROM sessions WHERE agent_id = :id"), {"id": str(agent_id)})
        await session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": str(agent_id)})
        await session.commit()


@pytest.mark.asyncio
async def test_intercept_response_returned_before_postgres_row_exists(client, agent_token, admin_token):
    """The audit_event_id in the response must be usable to find the row
    *eventually* (after the shipper runs) — proving the response doesn't
    block on the Postgres write."""
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(uuid.uuid4()),
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "agent_name": "claims-processing-agent",
        "tool_name": "wal_integration_probe_tool",
        "tool_parameters": {},
        "sequence_number": 1,
    })
    assert resp.status_code == 200
    event_id = resp.json()["audit_event_id"]
    assert event_id is not None

    from app.models.database import async_session_factory
    import asyncio
    for _ in range(20):
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT id FROM audit_events WHERE id = :id"), {"id": event_id}
            )
            if result.scalar_one_or_none():
                return
        await asyncio.sleep(0.05)
    pytest.fail("audit event never shipped to Postgres within 1s")


@pytest_asyncio.fixture(loop_scope="session")
async def observe_mode_agent_with_approved_tools():
    """Unlike observe_mode_agent (approved_tools='[]'), this fixture has a
    restricted approved_tools list, so it actually exercises the
    approved_tools gate in intercept.py -- observe_mode_agent's empty list
    sidesteps that branch entirely."""
    from app.models.database import async_session_factory
    agent_id = uuid.UUID("f2222222-2222-2222-2222-222222222222")
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools, governance_mode)
            VALUES (:id, 'test-agent-observe-approved-tools', 'test@test.com', 'active', '["read_file"]', 'observe')
            ON CONFLICT (id) DO UPDATE SET governance_mode = 'observe', approved_tools = '["read_file"]'
        """), {"id": str(agent_id)})
        await session.commit()
    yield agent_id
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM audit_events WHERE agent_id = :id"), {"id": str(agent_id)})
        await session.execute(text("DELETE FROM sessions WHERE agent_id = :id"), {"id": str(agent_id)})
        await session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": str(agent_id)})
        await session.commit()


@pytest.mark.asyncio
async def test_observe_mode_not_blocked_by_approved_tools_gate(
    client, agent_token, observe_mode_agent_with_approved_tools
):
    """An agent in observe mode with a restricted approved_tools list must NOT
    be hard-denied for calling a tool outside that list -- observe mode
    records but never blocks, per its documented semantics."""
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(uuid.uuid4()),
        "agent_id": str(observe_mode_agent_with_approved_tools),
        "agent_name": "test-agent-observe-approved-tools",
        "tool_name": "delete_database",
        "tool_parameters": {},
        "sequence_number": 1,
    })
    assert resp.json()["decision"] == "allow", (
        "observe mode must never block, even for a tool outside approved_tools"
    )


@pytest.mark.asyncio
async def test_observe_mode_always_allows_but_records_true_decision(
    client, agent_token, admin_token, observe_mode_agent
):
    await client.post("/policies", headers=admin_token, json={
        "name": "test_observe_mode_deny_all",
        "description": "Deny everything, to prove observe mode overrides it",
        "rule_type": "tool_denylist",
        "condition": {"blocked_tools": ["observe_mode_probe_tool"]},
        "action": "deny", "severity": "critical", "active": True,
    })
    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(uuid.uuid4()),
        "agent_id": str(observe_mode_agent),
        "agent_name": "test-agent-observe-intercept",
        "tool_name": "observe_mode_probe_tool",
        "tool_parameters": {},
        "sequence_number": 1,
    })
    assert resp.status_code == 200
    assert resp.json()["decision"] == "allow"

    from app.models.database import async_session_factory
    import asyncio
    for _ in range(20):
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT decision, enforced FROM audit_events WHERE id = :id"),
                {"id": resp.json()["audit_event_id"]},
            )
            row = result.one_or_none()
            if row is not None:
                assert row.decision == "deny"
                assert row.enforced is False
                return
        await asyncio.sleep(0.05)
    pytest.fail("audit event never shipped to Postgres within 1s")


@pytest.mark.asyncio
async def test_concurrent_intercept_same_new_session_does_not_500(client, agent_token):
    """Two truly concurrent /intercept calls sharing a brand-new session_id must
    both succeed (200) -- not race on ensure_session's unguarded SELECT-then-INSERT
    and 500 on a sessions_pkey unique violation."""
    session_id = str(uuid.uuid4())

    async def make_call(seq: int):
        return await client.post("/intercept", headers=agent_token, json={
            "session_id": session_id,
            "agent_id": "00000000-0000-0000-0000-000000000001",
            "agent_name": "claims-processing-agent",
            "tool_name": "read_file",
            "tool_parameters": {},
            "sequence_number": seq,
        })

    results = await asyncio.gather(make_call(1), make_call(2))
    statuses = [r.status_code for r in results]
    assert statuses == [200, 200], f"expected both calls to succeed, got {statuses}"


@pytest.mark.asyncio
async def test_deny_events_accumulate_session_risk_score(client, agent_token, admin_token):
    """Session.risk_score must increase as deny-triggering events accumulate in
    that session -- today RISK_SCORE_DELTA is written to audit_events.risk_delta
    per-event but never summed back onto the session row."""
    await client.post("/policies", headers=admin_token, json={
        "name": "test_risk_score_deny_tool",
        "description": "Always deny this tool",
        "rule_type": "tool_denylist",
        "condition": {"blocked_tools": ["test_risk_score_tool"]},
        "action": "deny", "active": True,
    })
    session_id = str(uuid.uuid4())
    for seq in range(1, 4):
        resp = await client.post("/intercept", headers=agent_token, json={
            "session_id": session_id,
            "agent_id": "00000000-0000-0000-0000-000000000001",
            "agent_name": "claims-processing-agent",
            "tool_name": "test_risk_score_tool",
            "tool_parameters": {},
            "sequence_number": seq,
        })
        assert resp.json()["decision"] == "deny"

    from app.models.database import async_session_factory
    for _ in range(20):
        async with async_session_factory() as db:
            result = await db.execute(
                text("SELECT risk_score FROM sessions WHERE id = :id"), {"id": session_id}
            )
            row = result.one_or_none()
            if row is not None and row.risk_score == 25 * 3:
                return
        await asyncio.sleep(0.05)
    pytest.fail(f"expected risk_score == 75, session row: {row}")
