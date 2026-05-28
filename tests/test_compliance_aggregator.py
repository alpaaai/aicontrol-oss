"""Tests for compliance report aggregator — Layer3Context building."""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from enterprise.compliance.aggregator import aggregate_audit_events, Layer3Context


def _make_row(**kwargs):
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one.return_value = value
    r.scalar_one_or_none.return_value = value
    return r


def _fetchall_result(rows):
    r = MagicMock()
    r.fetchall.return_value = rows
    return r


def _make_db(
    total=5, allowed=3, denied=2, reviewed=0,
    agent_rows=None, policy_rows=None, denied_sample_rows=None, hitl_count=0
):
    db = AsyncMock()

    call_index = [0]
    results = [
        _scalar_result(total),           # total intercepts
        _scalar_result(allowed),         # allowed
        _scalar_result(denied),          # denied
        _scalar_result(reviewed),        # reviewed
        _fetchall_result(agent_rows or []),
        _fetchall_result(policy_rows or []),
        _fetchall_result(denied_sample_rows or []),
        _scalar_result(hitl_count),      # active policy count
        _scalar_result(0),               # hitl_review_count (second scalar)
    ]

    async def _execute(stmt, *args, **kwargs):
        idx = call_index[0]
        call_index[0] += 1
        return results[idx] if idx < len(results) else _scalar_result(0)

    db.execute = _execute
    return db


DATE_FROM = date(2026, 1, 1)
DATE_TO = date(2026, 3, 31)


@pytest.mark.asyncio
async def test_aggregate_basic_counts():
    agent_rows = [
        _make_row(agent_name="loan-agent", calls=3, denied=2),
        _make_row(agent_name="support-agent", calls=2, denied=0),
    ]
    policy_rows = [
        _make_row(policy_name="deny_bulk_account_lookup", decision="deny", count=2),
    ]
    denied_sample_rows = [
        _make_row(
            created_at=datetime(2026, 2, 14, 9, 0, tzinfo=timezone.utc),
            agent_name="loan-agent",
            tool_name="bulk_query",
            policy_name="deny_bulk_account_lookup",
            tool_parameters={"query_type": "bulk"},
        ),
    ]

    db = _make_db(
        total=5, allowed=3, denied=2, reviewed=0,
        agent_rows=agent_rows,
        policy_rows=policy_rows,
        denied_sample_rows=denied_sample_rows,
        hitl_count=0,
    )

    ctx = await aggregate_audit_events(db, DATE_FROM, DATE_TO)

    assert isinstance(ctx, Layer3Context)
    assert ctx.total_intercepts == 5
    assert ctx.allowed == 3
    assert ctx.denied == 2
    assert ctx.reviewed == 0
    assert round(ctx.denial_rate_pct, 1) == 40.0


@pytest.mark.asyncio
async def test_aggregate_agent_summaries():
    agent_rows = [
        _make_row(agent_name="loan-agent", calls=3, denied=2),
        _make_row(agent_name="support-agent", calls=2, denied=0),
    ]
    db = _make_db(total=5, allowed=3, denied=2, agent_rows=agent_rows)

    ctx = await aggregate_audit_events(db, DATE_FROM, DATE_TO)

    assert len(ctx.agents) == 2
    names = [a["name"] for a in ctx.agents]
    assert "loan-agent" in names
    assert "support-agent" in names
    loan = next(a for a in ctx.agents if a["name"] == "loan-agent")
    assert loan["calls"] == 3
    assert loan["denied"] == 2


@pytest.mark.asyncio
async def test_aggregate_policies_fired():
    policy_rows = [
        _make_row(policy_name="deny_bulk_account_lookup", decision="deny", count=2),
    ]
    db = _make_db(total=5, allowed=3, denied=2, policy_rows=policy_rows)

    ctx = await aggregate_audit_events(db, DATE_FROM, DATE_TO)

    assert len(ctx.policies_fired) == 1
    assert ctx.policies_fired[0]["policy_name"] == "deny_bulk_account_lookup"
    assert ctx.policies_fired[0]["count"] == 2


@pytest.mark.asyncio
async def test_aggregate_zero_events_no_crash():
    db = _make_db(total=0, allowed=0, denied=0, reviewed=0)

    ctx = await aggregate_audit_events(db, DATE_FROM, DATE_TO)

    assert ctx.total_intercepts == 0
    assert ctx.denial_rate_pct == 0.0
    assert ctx.agents == []
    assert ctx.policies_fired == []
    assert ctx.denied_sample == []


@pytest.mark.asyncio
async def test_aggregate_date_range_stored():
    db = _make_db()

    ctx = await aggregate_audit_events(db, DATE_FROM, DATE_TO)

    assert ctx.date_from == DATE_FROM
    assert ctx.date_to == DATE_TO
