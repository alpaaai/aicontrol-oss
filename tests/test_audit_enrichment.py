import pytest
import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.models.database import async_session_factory


@pytest_asyncio.fixture(scope="session")
async def seed_audit_with_tool_response():
    sid = uuid.uuid4()
    eid = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO sessions (id, agent_id, started_at)
            VALUES (:sid, (SELECT id FROM agents LIMIT 1), NOW())
        """), {"sid": str(sid)})
        await db.execute(text("""
            INSERT INTO audit_events (id, session_id, sequence_number, tool_name,
                decision, tool_response, created_at)
            VALUES (:id, :sid, 1, 'write_file', 'deny',
                    '{"result":"blocked","reason":"policy_violation"}'::jsonb, NOW())
        """), {"id": str(eid), "sid": str(sid)})
        await db.commit()
    yield eid, sid
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
        await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(sid)})
        await db.commit()


@pytest.mark.asyncio
async def test_audit_events_include_tool_response(human_admin_token, seed_audit_with_tool_response):
    eid, _ = seed_audit_with_tool_response
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/audit-events", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    events = resp.json()["events"]
    ev = next(e for e in events if e["id"] == str(eid))
    assert "tool_response" in ev
    assert ev["tool_response"] is not None


@pytest.mark.asyncio
async def test_audit_events_tool_response_null_for_events_without_it(human_admin_token, seed_audit_events):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/audit-events", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    events = resp.json()["events"]
    seeded_ids = {str(eid) for eid in seed_audit_events}
    seeded_events = [e for e in events if e["id"] in seeded_ids]
    assert len(seeded_events) > 0
    for e in seeded_events:
        assert "tool_response" in e
        assert e["tool_response"] is None
