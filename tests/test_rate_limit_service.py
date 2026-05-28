"""Tests for P1-2: rate_limit_service COUNT queries and build_call_counts."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.rate_limit_service import (
    count_tool_calls_in_window,
    build_call_counts,
    WINDOW_INTERVALS,
)

AGENT_ID = "aaaaaaaa-0000-0000-0000-000000000001"
SESSION_ID = "bbbbbbbb-0000-0000-0000-000000000001"
TOOL = "query_credit_bureau"


def make_db_mock(count: int):
    scalar_mock = MagicMock()
    scalar_mock.scalar_one.return_value = count
    db = AsyncMock()
    db.execute.return_value = scalar_mock
    return db


@pytest.mark.asyncio
async def test_count_session_window_returns_correct_count():
    db = make_db_mock(7)
    result = await count_tool_calls_in_window(db, AGENT_ID, SESSION_ID, TOOL, "session")
    assert result == 7
    call_args = db.execute.call_args
    assert "session_id" in str(call_args)
    assert "agent_id" not in str(call_args)


@pytest.mark.asyncio
async def test_count_rolling_window_uses_agent_id():
    db = make_db_mock(3)
    result = await count_tool_calls_in_window(db, AGENT_ID, SESSION_ID, TOOL, "60m")
    assert result == 3
    call_args = db.execute.call_args
    assert "agent_id" in str(call_args)


@pytest.mark.asyncio
async def test_count_invalid_window_raises():
    db = make_db_mock(0)
    with pytest.raises(KeyError):
        await count_tool_calls_in_window(db, AGENT_ID, SESSION_ID, TOOL, "invalid")


@pytest.mark.asyncio
async def test_build_call_counts_skips_non_rate_limit_policies():
    db = make_db_mock(5)
    policies = [
        {"rule_type": "tool_denylist", "condition": {"blocked_tools": [TOOL]}},
    ]
    result = await build_call_counts(db, AGENT_ID, SESSION_ID, TOOL, policies)
    assert result == {}
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_build_call_counts_returns_count_for_matching_policy():
    db = make_db_mock(10)
    policies = [
        {
            "rule_type": "rate_limit",
            "condition": {
                "tools": [TOOL],
                "rate_limit": {"max_calls": 10, "window": "session"},
            },
        }
    ]
    result = await build_call_counts(db, AGENT_ID, SESSION_ID, TOOL, policies)
    assert result == {TOOL: 10}


@pytest.mark.asyncio
async def test_build_call_counts_does_not_query_twice_for_same_tool():
    db = make_db_mock(5)
    policies = [
        {
            "rule_type": "rate_limit",
            "condition": {
                "tools": [TOOL],
                "rate_limit": {"max_calls": 10, "window": "session"},
            },
        },
        {
            "rule_type": "rate_limit",
            "condition": {
                "tools": [TOOL],
                "rate_limit": {"max_calls": 5, "window": "session"},
            },
        },
    ]
    result = await build_call_counts(db, AGENT_ID, SESSION_ID, TOOL, policies)
    assert result == {TOOL: 5}
    assert db.execute.call_count == 1


@pytest.mark.asyncio
async def test_build_call_counts_empty_when_tool_not_in_policy():
    db = make_db_mock(99)
    policies = [
        {
            "rule_type": "rate_limit",
            "condition": {
                "tools": ["send_email"],
                "rate_limit": {"max_calls": 50, "window": "60m"},
            },
        }
    ]
    result = await build_call_counts(db, AGENT_ID, SESSION_ID, "query_credit_bureau", policies)
    assert result == {}
