"""Regression test: the test-agent-% cleanup must survive FK children.

audit_events.agent_id and .session_id are NO ACTION foreign keys, so a plain
DELETE FROM agents WHERE name LIKE 'test-agent-%' raises ForeignKeyViolationError
as soon as any test drives a real intercept for a test agent. That aborted the
session-scoped _cleanup_test_agents fixture and cascaded into hundreds of
"ERROR at setup" results. audit_events is append-only, so the event row itself is
never deleted: its nullable FK columns are cleared first, mirroring what
_cleanup_test_policies already does for policy_id/policy_name.
"""
import uuid

import pytest
from sqlalchemy import text

from app.models.database import async_session_factory
from tests.conftest import _cleanup_test_agent_rows

_PROBE_AGENT_NAME = "test-agent-fk-cleanup-probe"


async def _seed_agent_with_audit_event() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    agent_id, session_id, event_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, :name, 'pytest', 'active', CAST(:tools AS jsonb))
        """), {"id": agent_id, "name": _PROBE_AGENT_NAME, "tools": '["read_row"]'})
        await db.execute(text("""
            INSERT INTO sessions (id, agent_id) VALUES (:id, :agent_id)
        """), {"id": session_id, "agent_id": agent_id})
        await db.execute(text("""
            INSERT INTO audit_events
                (id, agent_id, session_id, sequence_number, tool_name, decision)
            VALUES (:id, :agent_id, :session_id, 1, 'read_row', 'allow')
        """), {"id": event_id, "agent_id": agent_id, "session_id": session_id})
        await db.commit()
    return agent_id, session_id, event_id


@pytest.mark.asyncio
async def test_cleanup_removes_test_agent_referenced_by_an_audit_event():
    agent_id, session_id, event_id = await _seed_agent_with_audit_event()

    async with async_session_factory() as db:
        await _cleanup_test_agent_rows(db)
        await db.commit()

    async with async_session_factory() as db:
        agents = (await db.execute(
            text("SELECT count(*) FROM agents WHERE id = :id"), {"id": agent_id}
        )).scalar_one()
        sessions = (await db.execute(
            text("SELECT count(*) FROM sessions WHERE id = :id"), {"id": session_id}
        )).scalar_one()
    assert agents == 0, "the test agent must be removed despite the audit event"
    assert sessions == 0, "its session must be removed too"


@pytest.mark.asyncio
async def test_cleanup_preserves_the_audit_event_row_itself():
    """audit_events is append-only: the row survives, only its nullable FK
    columns are cleared."""
    _agent_id, _session_id, event_id = await _seed_agent_with_audit_event()

    async with async_session_factory() as db:
        await _cleanup_test_agent_rows(db)
        await db.commit()

    async with async_session_factory() as db:
        row = (await db.execute(text(
            "SELECT agent_id, session_id, tool_name FROM audit_events WHERE id = :id"
        ), {"id": event_id})).fetchone()

    assert row is not None, "the audit event must never be deleted"
    assert row.agent_id is None
    assert row.session_id is None
    assert row.tool_name == "read_row"


@pytest.mark.asyncio
async def test_cleanup_leaves_non_test_agents_alone():
    keep_id = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, :name, 'pytest', 'active', CAST('[]' AS jsonb))
        """), {"id": keep_id, "name": f"keep-agent-{keep_id.hex[:8]}"})
        await db.commit()

    async with async_session_factory() as db:
        await _cleanup_test_agent_rows(db)
        await db.commit()

    async with async_session_factory() as db:
        still_there = (await db.execute(
            text("SELECT count(*) FROM agents WHERE id = :id"), {"id": keep_id}
        )).scalar_one()
        await db.execute(text("DELETE FROM agents WHERE id = :id"), {"id": keep_id})
        await db.commit()
    assert still_there == 1
