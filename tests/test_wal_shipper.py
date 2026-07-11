"""Tests for WalShipper — drains the WAL into Postgres, replays on startup (WS0)."""
import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(loop_scope="session")
async def clean_test_session(request):
    """agent_id/session_id fixed per test to make cleanup deterministic."""
    from app.models.database import async_session_factory
    agent_id = uuid.UUID("e1111111-1111-1111-1111-111111111111")
    session_id = uuid.UUID("e2222222-2222-2222-2222-222222222222")
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, 'wal-shipper-test-agent', 'test@test.com', 'active', '[]')
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(agent_id)})
        await session.execute(text("""
            INSERT INTO sessions (id, agent_id, status)
            VALUES (:id, :agent_id, 'active') ON CONFLICT (id) DO NOTHING
        """), {"id": str(session_id), "agent_id": str(agent_id)})
        await session.commit()
    yield agent_id, session_id
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM audit_events WHERE agent_id = :id"), {"id": str(agent_id)})
        await session.execute(text("DELETE FROM sessions WHERE agent_id = :id"), {"id": str(agent_id)})
        await session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": str(agent_id)})
        await session.commit()


@pytest.mark.asyncio
async def test_ship_once_drains_wal_lines_into_postgres(tmp_path, clean_test_session):
    from app.services.wal import WalWriter
    from app.services.wal_shipper import WalShipper
    from app.models.database import async_session_factory

    agent_id, session_id = clean_test_session
    wal_path = tmp_path / "audit.jsonl"
    writer = WalWriter(wal_path)
    event_id = writer.append({
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": "wal-shipper-test-agent", "tool_name": "shipper_test_tool",
        "tool_parameters": {}, "decision": "allow", "decision_reason": "default_allow",
        "sequence_number": 1, "duration_ms": 3,
    })

    shipper = WalShipper(wal_path=wal_path, session_factory=async_session_factory)
    shipped_count = await shipper._ship_once()
    assert shipped_count == 1

    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT tool_name, decision FROM audit_events WHERE id = :id"),
            {"id": str(event_id)},
        )
        row = result.one()
        assert row.tool_name == "shipper_test_tool"
        assert row.decision == "allow"


@pytest.mark.asyncio
async def test_ship_once_is_idempotent_on_checkpoint(tmp_path, clean_test_session):
    """A second _ship_once with no new lines ships nothing (checkpoint advanced)."""
    from app.services.wal import WalWriter
    from app.services.wal_shipper import WalShipper
    from app.models.database import async_session_factory

    agent_id, session_id = clean_test_session
    wal_path = tmp_path / "audit.jsonl"
    WalWriter(wal_path).append({
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": "wal-shipper-test-agent", "tool_name": "shipper_test_tool_2",
        "tool_parameters": {}, "decision": "allow", "decision_reason": "default_allow",
        "sequence_number": 1, "duration_ms": 3,
    })

    shipper = WalShipper(wal_path=wal_path, session_factory=async_session_factory)
    first = await shipper._ship_once()
    second = await shipper._ship_once()
    assert first == 1
    assert second == 0


@pytest.mark.asyncio
async def test_replay_and_start_ships_pre_existing_unshipped_lines(tmp_path, clean_test_session):
    """Simulates a crash: WAL has lines, checkpoint file doesn't exist yet.
    replay_and_start must ship them before beginning its periodic loop."""
    from app.services.wal import WalWriter
    from app.services.wal_shipper import WalShipper
    from app.models.database import async_session_factory

    agent_id, session_id = clean_test_session
    wal_path = tmp_path / "audit.jsonl"
    WalWriter(wal_path).append({
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": "wal-shipper-test-agent", "tool_name": "replay_test_tool",
        "tool_parameters": {}, "decision": "deny", "decision_reason": "test_replay",
        "sequence_number": 1, "duration_ms": 2,
    })

    shipper = WalShipper(wal_path=wal_path, session_factory=async_session_factory, ship_interval_s=999)
    await shipper.replay_and_start()
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM audit_events WHERE tool_name = 'replay_test_tool'")
            )
            assert result.scalar_one() == 1
    finally:
        await shipper.stop()
