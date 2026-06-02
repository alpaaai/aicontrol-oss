import pytest
import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.models.database import async_session_factory


@pytest_asyncio.fixture(scope="session")
async def seed_rich_session():
    sid = uuid.uuid4()
    eid1, eid2 = uuid.uuid4(), uuid.uuid4()
    rid = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO sessions (id, agent_id, trigger_context, status, completed_at, started_at)
            VALUES (:sid, (SELECT id FROM agents LIMIT 1),
                   'CI pipeline run', 'completed', NOW(), NOW() - INTERVAL '5 minutes')
        """), {"sid": str(sid)})
        for eid, seq in [(eid1, 1), (eid2, 2)]:
            await db.execute(text("""
                INSERT INTO audit_events (id, session_id, sequence_number, tool_name, decision, created_at)
                VALUES (:id, :sid, :seq, 'read_file', 'allow', NOW())
            """), {"id": str(eid), "sid": str(sid), "seq": seq})
        await db.execute(text("""
            INSERT INTO hitl_reviews (id, session_id, status, created_at)
            VALUES (:id, :sid, 'pending', NOW())
        """), {"id": str(rid), "sid": str(sid)})
        await db.commit()
    yield sid
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM hitl_reviews WHERE id = :id"), {"id": str(rid)})
        for eid in [eid1, eid2]:
            await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
        await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(sid)})
        await db.commit()


@pytest.mark.asyncio
async def test_session_list_includes_enriched_fields(human_admin_token, seed_rich_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/sessions", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    s = next(x for x in sessions if x["id"] == str(seed_rich_session))
    assert s["agent_name"] is not None
    assert s["status"] == "completed"
    assert s["completed_at"] is not None
    assert s["event_count"] == 2
    assert s["has_pending_review"] is True


@pytest.mark.asyncio
async def test_session_detail_includes_trigger_context(human_admin_token, seed_rich_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(
            f"/sessions/{seed_rich_session}/events",
            headers={"Authorization": f"Bearer {human_admin_token}"}
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trigger_context"] == "CI pipeline run"
