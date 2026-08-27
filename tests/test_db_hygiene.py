"""Tests for the canonical test/demo-artifact hygiene sweep (scripts/db_hygiene.py).

This module is the single source of truth for what counts as a leaked
test row and how to clean it -- used by both tests/conftest.py's autouse
cleanup fixtures and the standalone scripts/db_hygiene_check.py CLI.
"""
import uuid

import pytest
from sqlalchemy import text

from app.models.database import async_session_factory
from scripts import db_hygiene


@pytest.mark.asyncio
async def test_count_leaked_reports_zero_after_clean_all():
    # Other test files in the same session may have left test-* rows behind
    # (their own cleanup runs at session teardown, not between files), so
    # run clean_all first rather than assuming an already-clean DB.
    async with async_session_factory() as session:
        await db_hygiene.clean_all(session)
        counts = await db_hygiene.count_leaked(session)
    assert all(n == 0 for n in counts.values())
    # every sweep must actually be represented in the report -- an empty
    # dict would trivially satisfy the assertion above
    assert set(counts) == {sweep.label for sweep in db_hygiene.SWEEPS}


@pytest.mark.asyncio
async def test_clean_all_removes_a_leaked_test_agent():
    agent_id = str(uuid.uuid4())
    async with async_session_factory() as session:
        await session.execute(text(
            "INSERT INTO agents (id, name, owner, status, approved_tools) "
            "VALUES (:id, :name, 'nobody@test.dev', 'active', '[]'::jsonb)"
        ), {"id": agent_id, "name": f"test-agent-hygiene-leak-{agent_id[:8]}"})
        await session.commit()

        counts_before = await db_hygiene.count_leaked(session)
        assert counts_before["agents"] >= 1

        await db_hygiene.clean_all(session)

        result = await session.execute(
            text("SELECT 1 FROM agents WHERE id = :id"), {"id": agent_id}
        )
        assert result.first() is None


@pytest.mark.asyncio
async def test_clean_all_nulls_the_denormalized_agent_name_on_audit_events():
    """agent_id going NULL (FK-safe) must not leave the display-only
    agent_name column still reading 'test-agent-...' forever -- audit_events
    is append-only, so this is the only chance to clear it."""
    agent_id = str(uuid.uuid4())
    agent_name = f"test-agent-hygiene-name-leak-{agent_id[:8]}"
    event_id = str(uuid.uuid4())
    async with async_session_factory() as session:
        await session.execute(text(
            "INSERT INTO agents (id, name, owner, status, approved_tools) "
            "VALUES (:id, :name, 'nobody@test.dev', 'active', '[]'::jsonb)"
        ), {"id": agent_id, "name": agent_name})
        await session.execute(text(
            "INSERT INTO audit_events "
            "(id, sequence_number, agent_id, agent_name, tool_name, decision, bypass, enforced) "
            "VALUES (:id, 1, :agent_id, :agent_name, 'some_tool', 'allow', false, true)"
        ), {"id": event_id, "agent_id": agent_id, "agent_name": agent_name})
        await session.commit()

        await db_hygiene.clean_all(session)

        result = await session.execute(
            text("SELECT agent_id, agent_name FROM audit_events WHERE id = :id"),
            {"id": event_id},
        )
        row = result.first()
        assert row.agent_id is None
        assert row.agent_name is None


@pytest.mark.asyncio
async def test_clean_all_nulls_a_dangling_policy_name_on_audit_events():
    """If the parent test_ policy row was already deleted by a prior sweep,
    policy_id on the leftover audit_events row is already NULL -- the join
    in the policies sweep can no longer find it via policy_id, so it must
    also match on the denormalized policy_name directly."""
    event_id = str(uuid.uuid4())
    policy_name = f"test_hygiene_dangling_policy_{uuid.uuid4().hex[:8]}"
    async with async_session_factory() as session:
        await session.execute(text(
            "INSERT INTO audit_events "
            "(id, sequence_number, policy_id, policy_name, tool_name, decision, bypass, enforced) "
            "VALUES (:id, 1, NULL, :policy_name, 'some_tool', 'deny', false, true)"
        ), {"id": event_id, "policy_name": policy_name})
        await session.commit()

        await db_hygiene.clean_all(session)

        result = await session.execute(
            text("SELECT policy_name FROM audit_events WHERE id = :id"),
            {"id": event_id},
        )
        assert result.scalar() is None


@pytest.mark.asyncio
async def test_clean_all_is_resilient_to_a_failing_sweep(monkeypatch):
    """One sweeper raising must not prevent the others from running --
    this is the defensive property that fixes the historical bug where an
    FK violation in one cleanup aborted the whole session-scoped fixture
    and turned every later test into an 'ERROR at setup'."""
    agent_id = str(uuid.uuid4())

    async def _boom(session):
        raise RuntimeError("simulated failure")

    broken = [
        db_hygiene.Sweep(label="broken", count_sql="SELECT 0", clean=_boom)
    ] + list(db_hygiene.SWEEPS)
    monkeypatch.setattr(db_hygiene, "SWEEPS", broken)

    async with async_session_factory() as session:
        await session.execute(text(
            "INSERT INTO agents (id, name, owner, status, approved_tools) "
            "VALUES (:id, :name, 'nobody@test.dev', 'active', '[]'::jsonb)"
        ), {"id": agent_id, "name": f"test-agent-hygiene-leak-{agent_id[:8]}"})
        await session.commit()

        errors = await db_hygiene.clean_all(session)

        assert "broken" in errors
        result = await session.execute(
            text("SELECT 1 FROM agents WHERE id = :id"), {"id": agent_id}
        )
        assert result.first() is None
