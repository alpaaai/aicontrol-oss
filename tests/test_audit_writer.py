"""Tests for audit writer — event persistence."""
import uuid
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_write_event_calls_session_add():
    """write_event must add an AuditEvent to the session."""
    from app.services.audit_writer import write_event

    mock_session = AsyncMock()
    mock_session.add = AsyncMock()
    mock_session.flush = AsyncMock()

    event_id = await write_event(
        session=mock_session,
        session_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        agent_name="test-agent",
        tool_name="safe_tool",
        tool_parameters={"key": "value"},
        decision="allow",
        decision_reason="default_allow",
        sequence_number=1,
        duration_ms=42,
    )

    assert mock_session.add.called
    assert event_id is not None


@pytest.mark.asyncio
async def test_write_event_returns_uuid():
    """write_event must return a UUID for the created event."""
    from app.services.audit_writer import write_event

    mock_session = AsyncMock()
    mock_session.add = AsyncMock()
    mock_session.flush = AsyncMock()

    event_id = await write_event(
        session=mock_session,
        session_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        agent_name="test-agent",
        tool_name="safe_tool",
        tool_parameters={},
        decision="deny",
        decision_reason="tool_denylisted",
        sequence_number=2,
        duration_ms=10,
    )

    assert isinstance(event_id, uuid.UUID)


@pytest.mark.asyncio
async def test_write_event_persists_token_fields():
    """write_event must accept and persist input_tokens/output_tokens/cost_usd."""
    from app.services.audit_writer import write_event

    mock_session = AsyncMock()
    mock_session.add = AsyncMock()
    mock_session.flush = AsyncMock()

    await write_event(
        session=mock_session,
        session_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        agent_name="test-agent",
        tool_name="safe_tool",
        tool_parameters={},
        decision="allow",
        decision_reason="default_allow",
        sequence_number=1,
        duration_ms=10,
        input_tokens=120,
        output_tokens=45,
        cost_usd=0.0032,
    )

    written_event = mock_session.add.call_args[0][0]
    assert written_event.input_tokens == 120
    assert written_event.output_tokens == 45
    assert float(written_event.cost_usd) == 0.0032


@pytest.mark.asyncio
async def test_write_event_token_fields_default_none():
    """write_event must default token fields to None when not provided (backward compatible)."""
    from app.services.audit_writer import write_event

    mock_session = AsyncMock()
    mock_session.add = AsyncMock()
    mock_session.flush = AsyncMock()

    await write_event(
        session=mock_session,
        session_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        agent_name="test-agent",
        tool_name="safe_tool",
        tool_parameters={},
        decision="allow",
        decision_reason="default_allow",
        sequence_number=1,
        duration_ms=10,
    )

    written_event = mock_session.add.call_args[0][0]
    assert written_event.input_tokens is None
    assert written_event.output_tokens is None
    assert written_event.cost_usd is None
