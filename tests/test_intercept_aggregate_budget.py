"""An agent-level aggregate budget policy denies a call even when the specific
tool has no per-tool token_budget condition at all -- proving the standalone
"budget" rule_type is reachable end-to-end through /intercept, not just directly
against OPA (WS-F).

Isolation note. The previous version of this test seeded a fixed agent UUID and
POSTed a policy named test_aggregate_agent_budget that it never deleted. That
policy is agent-*scoped* but not agent-*specific*: while it sat active in OPA it
denied any agent whose cumulative spend crossed $100, so whichever intercept test
happened to run inside that window failed instead. The suite flaked on roughly
two runs in seven, rotating between this test and
test_intercept_wal_integration::test_observe_mode_always_allows_but_records_true_decision.
Both the agent and the policy are now unique per run and torn down explicitly, so
nothing survives the test that could govern another one.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

SEEDED_SPEND_USD = 150.0
BUDGET_CAP_USD = 100


@pytest_asyncio.fixture(loop_scope="session")
async def agent_with_high_spend(client, admin_token):
    """Seed one agent that has already spent over the cap, plus the policy that
    caps it. Both are unique to this run and removed afterwards."""
    from app.models.database import async_session_factory

    agent_id = uuid.uuid4()
    session_id = uuid.uuid4()
    # 'test-agent-' prefix puts leaks in reach of conftest's _cleanup_test_agent_rows;
    # 'test_' prefix does the same for the policy via _cleanup_test_policies.
    agent_name = f"test-agent-budget-{agent_id.hex[:8]}"
    policy_name = f"test_aggregate_agent_budget_{agent_id.hex[:8]}"

    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, :name, 'test@test.com', 'active', CAST('[]' AS jsonb))
        """), {"id": str(agent_id), "name": agent_name})
        await session.execute(text("""
            INSERT INTO sessions (id, agent_id, status) VALUES (:sid, :aid, 'active')
        """), {"sid": str(session_id), "aid": str(agent_id)})
        await session.execute(text("""
            INSERT INTO audit_events (id, session_id, agent_id, agent_name, tool_name,
                tool_parameters, decision, decision_reason, sequence_number, duration_ms,
                cost_usd, bypass, enforced)
            VALUES (:eid, :sid, :aid, :name, 'unrelated_tool_1', CAST('{}' AS jsonb),
                'allow', 'default_allow', 1, 5, :cost, false, true)
        """), {"eid": str(uuid.uuid4()), "sid": str(session_id), "aid": str(agent_id),
               "name": agent_name, "cost": SEEDED_SPEND_USD})
        await session.commit()

    resp = await client.post("/policies", headers=admin_token, json={
        "name": policy_name,
        "description": "Deny once this agent's total spend crosses the cap, any tool",
        "rule_type": "budget",
        "condition": {"scope": "agent", "max_cost_usd": BUDGET_CAP_USD,
                      "window": "session", "on_exceed": "deny"},
        "action": "deny", "severity": "high", "active": True,
    })
    assert resp.status_code == 201, resp.text
    policy_id = resp.json()["id"]

    try:
        yield agent_id, session_id, agent_name
    finally:
        # Delete the policy FIRST: leaving it active is what contaminated other
        # tests. Going through the API also pushes the updated bundle to OPA,
        # which a direct DB delete would not.
        await client.delete(f"/policies/{policy_id}", headers=admin_token)
        async with async_session_factory() as session:
            # audit_events is append-only -- clear the nullable FKs rather than
            # deleting the row, matching conftest's _cleanup_test_agent_rows.
            await session.execute(text(
                "UPDATE audit_events SET agent_id = NULL, session_id = NULL WHERE agent_id = :id"
            ), {"id": str(agent_id)})
            await session.execute(text("DELETE FROM sessions WHERE agent_id = :id"), {"id": str(agent_id)})
            await session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": str(agent_id)})
            await session.commit()


@pytest.mark.asyncio
async def test_agent_level_budget_denies_across_different_tools(
    client, agent_token, agent_with_high_spend
):
    """Prior spend (seeded above the cap) alone triggers the deny -- the budget
    check runs against cumulative spend so far, before this call's own cost is
    added, matching the existing per-tool build_token_budgets semantics."""
    agent_id, session_id, agent_name = agent_with_high_spend

    resp = await client.post("/intercept", headers=agent_token, json={
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": agent_name, "tool_name": "a_completely_different_tool_2",
        "tool_parameters": {}, "sequence_number": 2,
    })

    assert resp.status_code == 200
    assert resp.json()["decision"] == "deny"
    assert "budget_exceeded" in resp.json()["reason"]


@pytest.mark.asyncio
async def test_budget_policy_does_not_outlive_the_test_that_created_it(
    client, admin_token
):
    """Regression guard for the flake this file used to cause: no agent-scoped
    budget policy may be left active in the policy set between tests."""
    resp = await client.get("/policies", headers=admin_token)
    assert resp.status_code == 200
    leaked = [
        p for p in resp.json()
        if p.get("rule_type") == "budget"
        and p.get("active")
        and p.get("name", "").startswith("test_")
    ]
    assert leaked == [], f"leaked active budget policies: {[p['name'] for p in leaked]}"
