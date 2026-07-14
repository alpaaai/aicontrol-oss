"""demo_reset.py must only clear its own AGENT_ID's history, not every agent's."""
import uuid
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_demo_reset_does_not_wipe_other_agents_history():
    from app.models.database import async_session_factory
    from scripts.demo_reset import AGENT_ID

    other_agent_id = uuid.uuid4()
    other_session_id = uuid.uuid4()
    other_event_id = uuid.uuid4()

    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, 'test-other-agent-demo-reset', 'test@test.com', 'active', '[]'::jsonb)
        """), {"id": str(other_agent_id)})
        await db.execute(text("""
            INSERT INTO sessions (id, agent_id, started_at) VALUES (:sid, :aid, NOW())
        """), {"sid": str(other_session_id), "aid": str(other_agent_id)})
        await db.execute(text("""
            INSERT INTO audit_events (id, session_id, sequence_number, tool_name, decision, created_at)
            VALUES (:id, :sid, 1, 'unrelated_tool', 'allow', NOW())
        """), {"id": str(other_event_id), "sid": str(other_session_id)})
        await db.commit()

    from scripts.demo_reset import reset
    await reset()

    remaining_session = None
    remaining_event = None
    async with async_session_factory() as db:
        remaining_session = (await db.execute(
            text("SELECT id FROM sessions WHERE id = :sid"), {"sid": str(other_session_id)}
        )).scalar_one_or_none()
        remaining_event = (await db.execute(
            text("SELECT id FROM audit_events WHERE id = :eid"), {"eid": str(other_event_id)}
        )).scalar_one_or_none()

        # Cleanup regardless of assertion outcome
        await db.execute(text("DELETE FROM audit_events WHERE id = :eid"), {"eid": str(other_event_id)})
        await db.execute(text("DELETE FROM sessions WHERE id = :sid"), {"sid": str(other_session_id)})
        await db.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": str(other_agent_id)})
        await db.commit()

    assert remaining_session is not None, "demo_reset.py wiped an unrelated agent's session"
    assert remaining_event is not None, "demo_reset.py wiped an unrelated agent's audit event"
