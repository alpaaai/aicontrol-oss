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


@pytest.mark.asyncio
async def test_a_later_duplicate_line_does_not_roll_back_an_earlier_shipped_line(
    tmp_path, clean_test_session
):
    """3.5 fix: _ship_once used to write each line's checkpoint immediately
    after its own write_event() flush succeeded, but commit only once at the
    end of the whole batch, all inside one shared session. A later line's
    IntegrityError called session.rollback() on that same shared session --
    which discards every earlier line's flushed-but-uncommitted insert too --
    while the checkpoint had already advanced past those earlier lines. The
    result: the earlier row is gone from Postgres, but never re-shipped,
    because the checkpoint says it's done. This test pre-seeds a duplicate
    event_id as the SECOND line so it raises IntegrityError, and asserts the
    FIRST line's row still exists after the batch."""
    from app.services.wal import WalWriter
    from app.services.wal_shipper import WalShipper
    from app.models.database import async_session_factory

    agent_id, session_id = clean_test_session
    wal_path = tmp_path / "audit.jsonl"
    writer = WalWriter(wal_path)

    first_event_id = writer.append({
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": "wal-shipper-test-agent", "tool_name": "rollback_scope_test_first",
        "tool_parameters": {}, "decision": "allow", "decision_reason": "default_allow",
        "sequence_number": 1, "duration_ms": 3,
    })

    # Pre-insert a row under a fixed event_id directly, then append a WAL
    # line reusing that same event_id as the batch's second line -- its
    # write_event() will raise IntegrityError on the primary key.
    duplicate_event_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO audit_events
                (id, session_id, agent_id, agent_name, tool_name, tool_parameters,
                 decision, decision_reason, sequence_number, duration_ms)
            VALUES (:id, :session_id, :agent_id, 'wal-shipper-test-agent',
                    'rollback_scope_test_preexisting', '{}', 'allow', 'default_allow', 2, 1)
        """), {"id": str(duplicate_event_id), "session_id": str(session_id), "agent_id": str(agent_id)})
        await session.commit()

    with open(wal_path, "a") as f:
        f.write(json.dumps({
            "session_id": str(session_id), "agent_id": str(agent_id),
            "agent_name": "wal-shipper-test-agent", "tool_name": "rollback_scope_test_second",
            "tool_parameters": {}, "decision": "allow", "decision_reason": "default_allow",
            "sequence_number": 2, "duration_ms": 3,
            "event_id": str(duplicate_event_id), "wal_seq": 1,
        }) + "\n")

    shipper = WalShipper(wal_path=wal_path, session_factory=async_session_factory)
    await shipper._ship_once()

    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE id = :id"),
            {"id": str(first_event_id)},
        )
        assert result.scalar_one() == 1, (
            "first line's row was rolled back by the second line's IntegrityError "
            "despite its checkpoint already having advanced -- it will never be "
            "re-shipped"
        )
