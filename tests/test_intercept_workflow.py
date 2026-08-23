"""/intercept accepts a workflow and stores it on the audit event.

Deviation from the plan: the plan's version of these tests assumed an
`agent_token` fixture shaped `{"token": ..., "agent_id": ...}` and asserted
persistence by POSTing to the live server and immediately SELECTing the row.
Neither holds here — `agent_token` is a header dict with an *unscoped* token,
and allow/deny decisions land in the WAL first and reach Postgres only when
WalShipper next drains (0.2s later), so an immediate SELECT races the shipper.
These tests drive the same three write paths in-process instead, which is what
the phase-2 lesson about POST-then-assert flakes asks for.
"""
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.models.schemas import AuditEvent


def make_payload(**overrides):
    payload = {
        "session_id": str(uuid.uuid4()),
        "agent_id": str(uuid.uuid4()),
        "agent_name": "test-agent",
        "tool_name": "read_record",
        "tool_parameters": {},
        "sequence_number": 1,
    }
    payload.update(overrides)
    return payload


@contextmanager
def _mock_auth():
    from app.core.auth import require_agent
    from app.main import app

    app.dependency_overrides[require_agent] = lambda: {"role": "agent"}
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_agent, None)


def test_workflow_defaults_to_unassigned():
    from app.routers.intercept import InterceptRequest

    req = InterceptRequest(
        session_id=uuid.uuid4(), agent_id=uuid.uuid4(), agent_name="a",
        tool_name="t", sequence_number=1,
    )
    assert req.workflow == "unassigned"


@pytest.mark.asyncio
async def test_workflow_reaches_cedar_as_context():
    """A policy conditioning on context.workflow must be able to see it."""
    from app.main import app

    captured = {}

    async def fake_evaluate(**kwargs):
        captured.update(kwargs)
        return {"decision": "allow", "reason": "default_allow",
                "fired_policy_id": None, "fired_policy_name": None}

    wal_mock = MagicMock()
    wal_mock.append.return_value = uuid.uuid4()

    with patch("app.routers.intercept.evaluate", new=fake_evaluate), patch(
        "app.routers.intercept.wal_writer", new=wal_mock
    ), patch("app.routers.intercept.get_scoped_policies", new=AsyncMock(
        return_value=[]
    )), patch("app.routers.intercept.ensure_session", new=AsyncMock()), _mock_auth():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/intercept", json=make_payload(workflow="claims_intake")
            )

    assert resp.status_code == 200
    assert captured["context"]["workflow"] == "claims_intake"


@pytest.mark.asyncio
async def test_workflow_is_written_to_the_wal_on_the_allow_path():
    from app.main import app

    wal_mock = MagicMock()
    wal_mock.append.return_value = uuid.uuid4()

    with patch("app.routers.intercept.evaluate", new=AsyncMock(
        return_value={"decision": "allow", "reason": "default_allow"}
    )), patch("app.routers.intercept.wal_writer", new=wal_mock), patch(
        "app.routers.intercept.get_scoped_policies", new=AsyncMock(return_value=[])
    ), patch("app.routers.intercept.ensure_session", new=AsyncMock()), _mock_auth():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/intercept", json=make_payload(workflow="claims_intake")
            )

    assert resp.status_code == 200
    assert wal_mock.append.call_args.args[0]["workflow"] == "claims_intake"


@pytest.mark.asyncio
async def test_workflow_is_written_to_the_wal_on_the_approved_tools_deny():
    """The early approved-tools gate is a separate write path and must carry
    the workflow too, or a denied call goes missing from its own workflow."""
    from app.main import app
    from app.models.database import async_session_factory
    from sqlalchemy import text

    agent_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, 'test-agent-workflow-gate', 'tests', 'active',
                    CAST('["only_this_tool"]' AS jsonb))
        """), {"id": agent_id})
        await session.commit()

    wal_mock = MagicMock()
    wal_mock.append.return_value = uuid.uuid4()

    with patch("app.routers.intercept.wal_writer", new=wal_mock), patch(
        "app.routers.intercept.ensure_session", new=AsyncMock()
    ), _mock_auth():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/intercept",
                json=make_payload(
                    agent_id=str(agent_id), tool_name="some_other_tool",
                    workflow="claims_intake",
                ),
            )

    assert resp.status_code == 200
    assert resp.json()["decision"] == "deny"
    assert wal_mock.append.call_args.args[0]["workflow"] == "claims_intake"


@pytest.mark.asyncio
async def test_write_event_persists_the_workflow(db_session):
    """The review path writes synchronously through write_event."""
    from app.services.audit_writer import write_event

    event_id = await write_event(
        session=db_session,
        session_id=None,
        agent_id=None,
        agent_name="test-agent",
        tool_name="read_record",
        tool_parameters={},
        decision="review",
        decision_reason="policy_matched:x",
        sequence_number=1,
        duration_ms=1,
        workflow="claims_intake",
    )

    event = (await db_session.execute(
        select(AuditEvent).where(AuditEvent.id == event_id)
    )).scalar_one()
    assert event.workflow == "claims_intake"


@pytest.mark.asyncio
async def test_wal_shipper_carries_the_workflow_into_postgres(tmp_path):
    """The WAL is the allow/deny path's only route to Postgres — if the
    shipper drops the field, workflow is recorded for reviews only."""
    import json

    from app.services.wal_shipper import WalShipper

    wal_path = tmp_path / "audit.jsonl"
    wal_path.write_text(json.dumps({
        "wal_seq": 0,
        "event_id": str(uuid.uuid4()),
        "session_id": None,
        "agent_id": None,
        "agent_name": "test-agent",
        "tool_name": "read_record",
        "tool_parameters": {},
        "decision": "allow",
        "decision_reason": "default_allow",
        "sequence_number": 1,
        "duration_ms": 1,
        "workflow": "claims_intake",
    }) + "\n")

    captured = {}

    async def fake_write_event(**kwargs):
        captured.update(kwargs)
        return kwargs["event_id"]

    class _NullSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def commit(self):
            return None

    shipper = WalShipper(wal_path=wal_path, session_factory=lambda: _NullSession())
    with patch("app.services.wal_shipper.write_event", new=fake_write_event):
        shipped = await shipper._ship_once()

    assert shipped == 1
    assert captured["workflow"] == "claims_intake"
