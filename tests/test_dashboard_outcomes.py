"""Governance outcomes, grouped by workflow, phrased in business terms."""
import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.models.database import async_session_factory


@pytest_asyncio.fixture(scope="session")
async def seeded_events():
    """Two workflows, a mix of decisions, one event with no workflow assigned."""
    session_id = uuid.uuid4()
    event_ids = [uuid.uuid4() for _ in range(3)]
    now = datetime.utcnow()

    rows = [
        (event_ids[0], "release_payment", "review", "claims_intake"),
        (event_ids[1], "read_record", "deny", "claims_intake"),
        (event_ids[2], "export_records", "deny", None),
    ]

    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO sessions (id, agent_id, started_at)
            VALUES (:sid, (SELECT id FROM agents LIMIT 1), NOW())
        """), {"sid": str(session_id)})
        for seq, (eid, tool, decision, workflow) in enumerate(rows, 1):
            await db.execute(text("""
                INSERT INTO audit_events
                    (id, session_id, sequence_number, agent_id, tool_name, decision, workflow, created_at)
                VALUES
                    (:id, :sid, :seq, (SELECT id FROM agents LIMIT 1), :tool, :decision, :workflow, :created_at)
            """), {
                "id": str(eid), "sid": str(session_id), "seq": seq,
                "tool": tool, "decision": decision, "workflow": workflow,
                "created_at": now,
            })
        await db.commit()

    yield event_ids

    async with async_session_factory() as db:
        for eid in event_ids:
            await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
        await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(session_id)})
        await db.commit()


@pytest.mark.asyncio
async def test_outcomes_group_by_workflow(human_admin_token, seeded_events):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/outcomes?window=7d",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    workflows = {w["workflow"] for w in body["workflows"]}
    assert "claims_intake" in workflows


@pytest.mark.asyncio
async def test_review_on_a_payment_tool_reads_as_payment_held(human_admin_token, seeded_events):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/outcomes?window=7d",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    claims = next(w for w in resp.json()["workflows"] if w["workflow"] == "claims_intake")
    kinds = {o["kind"] for o in claims["outcomes"]}
    assert "payment_held" in kinds


@pytest.mark.asyncio
async def test_unassigned_workflow_is_its_own_group_not_dropped(human_admin_token, seeded_events):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/outcomes?window=7d",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    workflows = {w["workflow"] for w in resp.json()["workflows"]}
    assert "unassigned" in workflows


@pytest.mark.asyncio
async def test_empty_window_returns_empty_workflows_not_an_error(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/outcomes?window=1h",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    assert isinstance(resp.json()["workflows"], list)


@pytest_asyncio.fixture(scope="session")
async def seeded_events_with_agents_and_hitl():
    """Events with explicit agent_name, plus one HITLReview for held count test."""
    session_id = uuid.uuid4()
    agent_name = f"test-agent-{uuid.uuid4().hex[:8]}"
    event_ids = [uuid.uuid4() for _ in range(3)]
    hitl_id = uuid.uuid4()
    now = datetime.utcnow()

    async with async_session_factory() as db:
        # Get agent ID
        agent_result = await db.execute(text("SELECT id FROM agents LIMIT 1"))
        agent_id = agent_result.scalar()

        await db.execute(text("""
            INSERT INTO sessions (id, agent_id, started_at)
            VALUES (:sid, :aid, NOW())
        """), {"sid": str(session_id), "aid": str(agent_id)})

        for seq, eid in enumerate(event_ids, 1):
            await db.execute(text("""
                INSERT INTO audit_events
                    (id, session_id, sequence_number, agent_id, agent_name, tool_name, decision, workflow, created_at)
                VALUES
                    (:id, :sid, :seq, :aid, :agent_name, :tool, :decision, :workflow, :created_at)
            """), {
                "id": str(eid), "sid": str(session_id), "seq": seq, "aid": str(agent_id),
                "agent_name": agent_name,
                "tool": f"tool_{seq}",
                "decision": "allow" if seq == 1 else ("deny" if seq == 2 else "review"),
                "workflow": "test_workflow",
                "created_at": now,
            })

        # Create one HITL review for the third event (review decision)
        await db.execute(text("""
            INSERT INTO hitl_reviews (id, audit_event_id, status, created_at)
            VALUES (:id, :eid, 'pending', NOW())
        """), {"id": str(hitl_id), "eid": str(event_ids[2])})

        await db.commit()

    yield agent_name, event_ids, hitl_id

    # Cleanup
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM hitl_reviews WHERE id = :id"), {"id": str(hitl_id)})
        for eid in event_ids:
            await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
        await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(session_id)})
        await db.commit()


@pytest.mark.asyncio
async def test_outcomes_includes_per_agent_breakdown(human_admin_token, seeded_events_with_agents_and_hitl):
    agent_name, event_ids, _ = seeded_events_with_agents_and_hitl
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/outcomes?window=7d",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "agents" in body
    assert isinstance(body["agents"], list)


@pytest.mark.asyncio
async def test_agent_outcome_shape_correct(human_admin_token, seeded_events_with_agents_and_hitl):
    agent_name, event_ids, _ = seeded_events_with_agents_and_hitl
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/outcomes?window=7d",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    body = resp.json()
    agents = body["agents"]
    agent = next((a for a in agents if a["agent_name"] == agent_name), None)
    assert agent is not None
    assert "calls" in agent
    assert "held_for_approval" in agent
    assert "denied" in agent


@pytest.mark.asyncio
async def test_agent_outcome_counts_correct(human_admin_token, seeded_events_with_agents_and_hitl):
    agent_name, event_ids, _ = seeded_events_with_agents_and_hitl
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/outcomes?window=7d",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    body = resp.json()
    agents = body["agents"]
    agent = next((a for a in agents if a["agent_name"] == agent_name), None)
    # 3 calls total, 1 denied, 1 held (pending review)
    assert agent["calls"] == 3
    assert agent["denied"] == 1
    assert agent["held_for_approval"] == 1


@pytest.mark.asyncio
async def test_agents_sorted_by_calls_descending(human_admin_token, seeded_events_with_agents_and_hitl):
    _, _, _ = seeded_events_with_agents_and_hitl
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/outcomes?window=7d",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    body = resp.json()
    agents = body["agents"]
    if len(agents) > 1:
        calls = [a["calls"] for a in agents]
        assert calls == sorted(calls, reverse=True)
