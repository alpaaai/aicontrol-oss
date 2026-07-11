"""Tests for the local append-only WAL writer (WS0)."""
import json
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def wal_path(tmp_path):
    return tmp_path / "audit.jsonl"


def test_append_returns_a_uuid_and_writes_one_line(wal_path):
    from app.services.wal import WalWriter

    writer = WalWriter(wal_path)
    event_id = writer.append({
        "session_id": str(uuid.uuid4()),
        "agent_id": str(uuid.uuid4()),
        "agent_name": "test-agent",
        "tool_name": "test_tool",
        "tool_parameters": {"x": 1},
        "decision": "allow",
        "decision_reason": "default_allow",
        "sequence_number": 1,
        "duration_ms": 5,
    })

    assert isinstance(event_id, uuid.UUID)
    lines = wal_path.read_text().strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event_id"] == str(event_id)
    assert parsed["tool_name"] == "test_tool"
    assert parsed["wal_seq"] == 0


def test_append_increments_wal_seq_across_calls(wal_path):
    from app.services.wal import WalWriter

    writer = WalWriter(wal_path)
    writer.append({"tool_name": "a", "session_id": None, "agent_id": None,
                    "agent_name": None, "tool_parameters": {}, "decision": "allow",
                    "decision_reason": "x", "sequence_number": 1, "duration_ms": 1})
    writer.append({"tool_name": "b", "session_id": None, "agent_id": None,
                    "agent_name": None, "tool_parameters": {}, "decision": "allow",
                    "decision_reason": "x", "sequence_number": 2, "duration_ms": 1})

    lines = [json.loads(l) for l in wal_path.read_text().strip().splitlines()]
    assert [l["wal_seq"] for l in lines] == [0, 1]


def test_append_creates_parent_directory(tmp_path):
    from app.services.wal import WalWriter

    nested = tmp_path / "nested" / "dir" / "audit.jsonl"
    writer = WalWriter(nested)
    writer.append({"tool_name": "a", "session_id": None, "agent_id": None,
                    "agent_name": None, "tool_parameters": {}, "decision": "allow",
                    "decision_reason": "x", "sequence_number": 1, "duration_ms": 1})
    assert nested.exists()


def test_sum_unshipped_tokens_and_cost_for_session_tool(wal_path):
    """Same undercounting-during-shipping-lag gap that
    count_unshipped_for_session_tool closes for rate_limit counts also
    applies to token_budget cumulative sums — a burst of calls within the
    WAL shipper's poll interval must still be seen by build_token_budgets."""
    from app.services.wal import WalWriter, sum_unshipped_for_session_tool

    writer = WalWriter(wal_path)
    sid = str(uuid.uuid4())
    writer.append({
        "session_id": sid, "agent_id": str(uuid.uuid4()), "agent_name": "a",
        "tool_name": "expensive_llm_probe_tool", "tool_parameters": {}, "decision": "allow",
        "decision_reason": "x", "sequence_number": 1, "duration_ms": 1,
        "input_tokens": 80000, "output_tokens": 1000, "cost_usd": 2.5,
    })
    writer.append({
        "session_id": sid, "agent_id": str(uuid.uuid4()), "agent_name": "a",
        "tool_name": "expensive_llm_probe_tool", "tool_parameters": {}, "decision": "allow",
        "decision_reason": "x", "sequence_number": 2, "duration_ms": 1,
        "input_tokens": 30000, "output_tokens": 500, "cost_usd": 1.5,
    })
    # unrelated tool in the same session — must not be included
    writer.append({
        "session_id": sid, "agent_id": str(uuid.uuid4()), "agent_name": "a",
        "tool_name": "other_tool", "tool_parameters": {}, "decision": "allow",
        "decision_reason": "x", "sequence_number": 3, "duration_ms": 1,
        "input_tokens": 999999, "output_tokens": 999999, "cost_usd": 999.0,
    })

    tokens, cost = sum_unshipped_for_session_tool(wal_path, sid, "expensive_llm_probe_tool")
    assert tokens == 80000 + 1000 + 30000 + 500
    assert cost == 4.0
