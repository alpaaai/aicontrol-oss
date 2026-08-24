"""GET /policies/{id}/activity — what this policy did last week."""
import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(loop_scope="session")
async def make_policy():
    from app.models.database import async_session_factory

    created_ids = []

    async def _make(**columns):
        policy_id = uuid.uuid4()
        columns.setdefault("condition", "{}")
        cols = {"id": policy_id, "active": True, "library": False, "priority": 100, **columns}
        names = ", ".join(cols)
        binds = [f"CAST(:{k} AS jsonb)" if k == "condition" else f":{k}" for k in cols]
        async with async_session_factory() as session:
            await session.execute(
                text(f"INSERT INTO policies ({names}) VALUES ({', '.join(binds)})"), cols
            )
            await session.commit()
        created_ids.append(policy_id)
        return policy_id

    yield _make

    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        for pid in created_ids:
            await session.execute(text("DELETE FROM policies WHERE id = :id"), {"id": pid})
        await session.commit()


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_activity_events():
    """Three calls in scope for the target agent+tool, one of which fired
    the policy (decision=review + matching policy_id)."""
    from app.models.database import async_session_factory

    agent_name = f"test-agent-activity-{uuid.uuid4().hex[:8]}"
    session_id = uuid.uuid4()
    event_ids = [uuid.uuid4() for _ in range(3)]
    now = datetime.utcnow()

    async with async_session_factory() as db:
        agent_id = (await db.execute(text(
            "INSERT INTO agents (id, name, owner, status) VALUES (gen_random_uuid(), :name, 'tests', 'active') RETURNING id"
        ), {"name": agent_name})).scalar()
        await db.execute(text(
            "INSERT INTO sessions (id, agent_id, started_at) VALUES (:sid, :aid, NOW())"
        ), {"sid": str(session_id), "aid": str(agent_id)})
        await db.commit()

    yield agent_name, agent_id, session_id, event_ids, now

    async with async_session_factory() as db:
        for eid in event_ids:
            await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
        await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(session_id)})
        await db.execute(text("DELETE FROM agents WHERE id = :id"), {"id": str(agent_id)})
        await db.commit()


@pytest.mark.asyncio
async def test_activity_counts_fired_and_calls_evaluated(
    client, admin_token, make_policy, seeded_activity_events
):
    agent_name, agent_id, session_id, event_ids, now = seeded_activity_events
    policy_id = await make_policy(
        name=f"test-activity-review-{uuid.uuid4().hex[:8]}",
        principal_type="agent",
        principal_id=agent_name,
        action_tool="release_payment",
        resource_system="guidewire",
        effect="review",
    )

    from app.models.database import async_session_factory
    async with async_session_factory() as db:
        rows = [
            (event_ids[0], "review", str(policy_id)),
            (event_ids[1], "allow", None),
            (event_ids[2], "allow", None),
        ]
        for seq, (eid, decision, pid) in enumerate(rows, 1):
            await db.execute(text("""
                INSERT INTO audit_events
                    (id, session_id, sequence_number, agent_id, agent_name, tool_name, decision, policy_id, created_at)
                VALUES
                    (:id, :sid, :seq, :aid, :aname, 'release_payment', :decision, :pid, :created_at)
            """), {
                "id": str(eid), "sid": str(session_id), "seq": seq, "aid": str(agent_id),
                "aname": agent_name, "decision": decision, "pid": pid, "created_at": now,
            })
        await db.commit()

    resp = await client.get(f"/policies/{policy_id}/activity?window=7d", headers=admin_token)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["window"] == "7d"
    assert body["fired"] == 1
    assert body["calls_evaluated"] == 3


@pytest.mark.asyncio
async def test_unknown_policy_returns_404(client, admin_token):
    resp = await client.get(f"/policies/{uuid.uuid4()}/activity", headers=admin_token)
    assert resp.status_code == 404
