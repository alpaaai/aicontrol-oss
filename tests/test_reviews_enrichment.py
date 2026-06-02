import pytest
import uuid
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.models.database import async_session_factory


@pytest_asyncio.fixture(scope="session")
async def seed_review_with_context():
    sid = uuid.uuid4()
    eid = uuid.uuid4()
    rid = uuid.uuid4()
    deadline = datetime.utcnow() + timedelta(hours=2)
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO sessions (id, agent_id, started_at)
            VALUES (:sid, (SELECT id FROM agents LIMIT 1), NOW())
        """), {"sid": str(sid)})
        await db.execute(text("""
            INSERT INTO audit_events (id, session_id, sequence_number, tool_name,
                tool_parameters, decision, created_at)
            VALUES (:id, :sid, 1, 'write_file', '{"path":"/etc/passwd"}'::jsonb, 'review', NOW())
        """), {"id": str(eid), "sid": str(sid)})
        await db.execute(text("""
            INSERT INTO hitl_reviews (id, audit_event_id, session_id, status,
                response_deadline, assigned_to, created_at)
            VALUES (:id, :eid, :sid, 'pending', :deadline, 'security@example.com', NOW())
        """), {"id": str(rid), "eid": str(eid), "sid": str(sid), "deadline": deadline})
        await db.commit()
    yield rid
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM hitl_reviews WHERE id = :id"), {"id": str(rid)})
        await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
        await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(sid)})
        await db.commit()


@pytest.mark.asyncio
async def test_review_list_includes_enriched_fields(human_admin_token, seed_review_with_context):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/reviews", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    reviews = resp.json()
    r = next(x for x in reviews if x["id"] == str(seed_review_with_context))
    assert r["response_deadline"] is not None
    assert r["assigned_to"] == "security@example.com"
    assert r["tool_name"] == "write_file"
    assert r["tool_parameters"] is not None
