"""Observe mode and session risk accumulation, driven in-process.

Replaces two cases from tests/test_intercept_wal_integration.py that POSTed a
policy to the shared live server and then asserted the decision an /intercept
call returned. Both flaked in this session's runs ("expected deny, got allow")
-- the same order-dependent shape phase 2 removed elsewhere. The decision here
comes from a stubbed engine call rather than from a policy row that has to
reach a server's cache first, so the assertions hold in any run order.

The behaviours under test are unchanged: observe mode reports allow while
recording the true decision as unenforced, and every deny adds its risk delta
to the session row.
"""
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

OBSERVE_AGENT_ID = uuid.UUID("f3333333-3333-3333-3333-333333333333")
GOVERN_AGENT_ID = uuid.UUID("f4444444-4444-4444-4444-444444444444")


@contextmanager
def _mock_auth():
    from app.core.auth import require_agent
    from app.main import app

    app.dependency_overrides[require_agent] = lambda: {"role": "agent"}
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_agent, None)


async def _insert_agent(agent_id: uuid.UUID, name: str, mode: str) -> None:
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools, governance_mode)
            VALUES (:id, :name, 'tests', 'active', '[]', :mode)
            ON CONFLICT (id) DO UPDATE SET governance_mode = EXCLUDED.governance_mode
        """), {"id": agent_id, "name": name, "mode": mode})
        await session.commit()


async def _delete_agent(agent_id: uuid.UUID) -> None:
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE audit_events SET agent_id = NULL WHERE agent_id = :id"),
            {"id": agent_id},
        )
        await session.execute(
            text("UPDATE audit_events SET session_id = NULL WHERE session_id IN "
                 "(SELECT id FROM sessions WHERE agent_id = :id)"),
            {"id": agent_id},
        )
        await session.execute(text("DELETE FROM sessions WHERE agent_id = :id"), {"id": agent_id})
        await session.execute(text("DELETE FROM agents WHERE id = :id"), {"id": agent_id})
        await session.commit()


@pytest_asyncio.fixture(loop_scope="session")
async def observe_agent():
    await _insert_agent(OBSERVE_AGENT_ID, "test-agent-observe-inproc", "observe")
    yield OBSERVE_AGENT_ID
    await _delete_agent(OBSERVE_AGENT_ID)


@pytest_asyncio.fixture(loop_scope="session")
async def govern_agent():
    await _insert_agent(GOVERN_AGENT_ID, "test-agent-govern-inproc", "govern")
    yield GOVERN_AGENT_ID
    await _delete_agent(GOVERN_AGENT_ID)


def _payload(agent_id, session_id, seq=1, tool="observe_mode_probe_tool"):
    return {
        "session_id": str(session_id),
        "agent_id": str(agent_id),
        "agent_name": "test-agent-inproc",
        "tool_name": tool,
        "tool_parameters": {},
        "sequence_number": seq,
    }


@pytest.mark.asyncio
async def test_observe_mode_returns_allow_but_records_the_true_deny(observe_agent):
    """Observe mode never blocks. The audit record still carries the decision
    the engine actually reached, marked unenforced -- that is the whole point
    of the mode, and losing it would make observe mode worthless."""
    from app.main import app

    wal_mock = MagicMock()
    wal_mock.append.return_value = uuid.uuid4()

    with patch("app.routers.intercept.evaluate", new=AsyncMock(
        return_value={"decision": "deny", "reason": "policy_matched:probe",
                      "fired_policy_id": None, "fired_policy_name": "probe"}
    )), patch("app.routers.intercept.wal_writer", new=wal_mock), patch(
        "app.routers.intercept.get_scoped_policies", new=AsyncMock(return_value=[])
    ), _mock_auth():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/intercept", json=_payload(observe_agent, uuid.uuid4())
            )

    assert resp.status_code == 200
    assert resp.json()["decision"] == "allow"

    written = wal_mock.append.call_args.args[0]
    assert written["decision"] == "deny"
    assert written["enforced"] is False


@pytest.mark.asyncio
async def test_govern_mode_returns_the_true_deny(govern_agent):
    from app.main import app

    wal_mock = MagicMock()
    wal_mock.append.return_value = uuid.uuid4()

    with patch("app.routers.intercept.evaluate", new=AsyncMock(
        return_value={"decision": "deny", "reason": "policy_matched:probe",
                      "fired_policy_id": None, "fired_policy_name": "probe"}
    )), patch("app.routers.intercept.wal_writer", new=wal_mock), patch(
        "app.routers.intercept.get_scoped_policies", new=AsyncMock(return_value=[])
    ), _mock_auth():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/intercept", json=_payload(govern_agent, uuid.uuid4())
            )

    assert resp.json()["decision"] == "deny"
    assert wal_mock.append.call_args.args[0]["enforced"] is True


@pytest.mark.asyncio
async def test_deny_events_accumulate_session_risk_score(govern_agent):
    """RISK_SCORE_DELTA["deny"] is 25 per event, summed onto the session row."""
    from app.main import app
    from app.models.database import async_session_factory
    from app.routers.intercept import RISK_SCORE_DELTA

    session_id = uuid.uuid4()
    wal_mock = MagicMock()
    wal_mock.append.return_value = uuid.uuid4()

    with patch("app.routers.intercept.evaluate", new=AsyncMock(
        return_value={"decision": "deny", "reason": "policy_matched:probe",
                      "fired_policy_id": None, "fired_policy_name": "probe"}
    )), patch("app.routers.intercept.wal_writer", new=wal_mock), patch(
        "app.routers.intercept.get_scoped_policies", new=AsyncMock(return_value=[])
    ), _mock_auth():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for seq in (1, 2, 3):
                resp = await client.post(
                    "/intercept",
                    json=_payload(govern_agent, session_id, seq=seq,
                                  tool="risk_score_probe_tool"),
                )
                assert resp.json()["decision"] == "deny"

    async with async_session_factory() as db:
        risk = (await db.execute(
            text("SELECT risk_score FROM sessions WHERE id = :id"), {"id": session_id}
        )).scalar_one()

    assert risk == RISK_SCORE_DELTA["deny"] * 3
