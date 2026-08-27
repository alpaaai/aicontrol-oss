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
