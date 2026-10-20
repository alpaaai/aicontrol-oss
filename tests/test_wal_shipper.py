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


def _wal_line(session_id, agent_id, tool_name, seq, event_id=None, **overrides):
    return {
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": "wal-shipper-test-agent", "tool_name": tool_name,
        "tool_parameters": {}, "decision": "allow", "decision_reason": "default_allow",
        "sequence_number": seq, "duration_ms": 1,
        "event_id": str(event_id or uuid.uuid4()), "wal_seq": seq,
        **overrides,
    }


def _write_lines(path, lines):
    with open(path, "a") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


@pytest.mark.asyncio
async def test_missing_session_row_is_retried_not_dropped(tmp_path, clean_test_session):
    """The request that appended a WAL line has not necessarily committed its
    sessions row yet when the shipper runs. The FK IntegrityError that causes
    must not be treated as a harmless duplicate -- the checkpoint must stay put
    so the line ships once the session row exists."""
    from app.models.database import async_session_factory
    from app.services.wal_shipper import WalShipper

    agent_id, _ = clean_test_session
    late_session_id = uuid.UUID("e3333333-3333-3333-3333-333333333333")
    wal_path = tmp_path / "audit.jsonl"
    event_id = uuid.uuid4()
    _, ok_session_id = clean_test_session
    _write_lines(wal_path, [
        _wal_line(late_session_id, agent_id, "fk_race_tool", 0, event_id),
        _wal_line(ok_session_id, agent_id, "fk_race_followup_tool", 1),
    ])

    shipper = WalShipper(wal_path=wal_path, session_factory=async_session_factory)
    try:
        assert await shipper._ship_once() == 0

        async with async_session_factory() as session:
            await session.execute(text(
                "INSERT INTO sessions (id, agent_id, status) VALUES (:id, :a, 'active')"
            ), {"id": str(late_session_id), "a": str(agent_id)})
            await session.commit()

        assert await shipper._ship_once() == 2
        async with async_session_factory() as session:
            count = (await session.execute(
                text("SELECT COUNT(*) FROM audit_events WHERE id = :id"), {"id": str(event_id)}
            )).scalar_one()
        assert count == 1
    finally:
        async with async_session_factory() as session:
            await session.execute(text("DELETE FROM audit_events WHERE session_id = :id"), {"id": str(late_session_id)})
            await session.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(late_session_id)})
            await session.commit()


@pytest.mark.asyncio
async def test_unshippable_line_is_dead_lettered_and_later_lines_still_ship(tmp_path, clean_test_session):
    """A line that can never ship (here: references a session that does not
    exist) must not block every later audit event forever. After max_attempts
    it moves to a dead-letter file and the checkpoint advances."""
    from app.models.database import async_session_factory
    from app.services.wal_shipper import WalShipper

    agent_id, session_id = clean_test_session
    wal_path = tmp_path / "audit.jsonl"
    bad_event, good_event = uuid.uuid4(), uuid.uuid4()
    _write_lines(wal_path, [
        _wal_line(uuid.uuid4(), agent_id, "poison_tool", 0, bad_event),
        _wal_line(session_id, agent_id, "after_poison_tool", 1, good_event),
    ])

    shipper = WalShipper(wal_path=wal_path, session_factory=async_session_factory, max_attempts=2)
    await shipper._ship_once()
    await shipper._ship_once()
    await shipper._ship_once()

    async with async_session_factory() as session:
        shipped = (await session.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE id = :id"), {"id": str(good_event)}
        )).scalar_one()
    assert shipped == 1
    dead_letter = wal_path.with_suffix(wal_path.suffix + ".deadletter")
    assert dead_letter.exists()
    assert str(bad_event) in dead_letter.read_text()


@pytest.mark.asyncio
async def test_malformed_wal_line_does_not_block_shipping(tmp_path, clean_test_session):
    """A crash mid-write can leave a torn trailing line. json.loads on it used
    to raise out of _ship_once on every cycle, stalling shipping permanently."""
    from app.models.database import async_session_factory
    from app.services.wal_shipper import WalShipper

    agent_id, session_id = clean_test_session
    wal_path = tmp_path / "audit.jsonl"
    event_id = uuid.uuid4()
    _write_lines(wal_path, [_wal_line(session_id, agent_id, "torn_line_tool", 0, event_id)])
    with open(wal_path, "a") as f:
        f.write('{"session_id": "abc", "tool_na')

    shipper = WalShipper(wal_path=wal_path, session_factory=async_session_factory)
    assert await shipper._ship_once() == 1


@pytest.mark.asyncio
async def test_shipped_lines_are_compacted_out_of_the_wal(tmp_path, clean_test_session):
    """The WAL used to grow forever, and every request re-parsed all of it for
    the unshipped-count lookups. Once lines are shipped they must be dropped."""
    from app.models.database import async_session_factory
    from app.services.wal import WalWriter
    from app.services.wal_shipper import WalShipper

    agent_id, session_id = clean_test_session
    wal_path = tmp_path / "audit.jsonl"
    writer = WalWriter(wal_path)
    for i in range(3):
        writer.append({
            "session_id": str(session_id), "agent_id": str(agent_id),
            "agent_name": "wal-shipper-test-agent", "tool_name": "compact_tool",
            "tool_parameters": {}, "decision": "allow", "decision_reason": "default_allow",
            "sequence_number": i, "duration_ms": 1,
        })

    shipper = WalShipper(wal_path=wal_path, session_factory=async_session_factory, compact_threshold_bytes=0)
    assert await shipper._ship_once() == 3
    assert wal_path.read_text() == ""

    # A restarted writer must not reuse sequence numbers at or below the
    # checkpoint, or its lines would be treated as already shipped.
    restarted = WalWriter(wal_path)
    restarted.append({
        "session_id": str(session_id), "agent_id": str(agent_id),
        "agent_name": "wal-shipper-test-agent", "tool_name": "compact_tool",
        "tool_parameters": {}, "decision": "allow", "decision_reason": "default_allow",
        "sequence_number": 9, "duration_ms": 1,
    })
    assert await shipper._ship_once() == 1


def test_pending_count_reports_unshipped_lines(tmp_path):
    from app.services.wal_shipper import WalShipper
    wal_path = tmp_path / "audit.jsonl"
    _write_lines(wal_path, [
        _wal_line(uuid.uuid4(), uuid.uuid4(), "t", 0),
        _wal_line(uuid.uuid4(), uuid.uuid4(), "t", 1),
    ])
    wal_path.with_suffix(".jsonl.checkpoint").write_text("0")
    shipper = WalShipper(wal_path=wal_path, session_factory=None)
    assert shipper.pending_count() == 1
