"""Integration tests for P1-2 rate-limit enforcement in the intercept loop.

Uses ASGITransport (in-process) so the worktree's intercept.py is tested directly.
Seeds audit_events in the DB to simulate prior tool calls, then asserts that
call N+1 is denied with the correct reason and policy_id.
"""
import uuid
from contextlib import contextmanager

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

# Fixed UUIDs so teardown is deterministic
RATE_TEST_AGENT_ID = uuid.UUID("d1111111-1111-1111-1111-111111111111")
RATE_TEST_SESSION_A = uuid.UUID("d2222222-2222-2222-2222-222222222222")
RATE_TEST_SESSION_B = uuid.UUID("d3333333-3333-3333-3333-333333333333")
RATE_TOOL = "query_credit_bureau"
RATE_POLICY_NAME = "test_rate_limit_credit_query"


@contextmanager
def _mock_agent():
    from app.main import app
    from app.core.auth import require_agent
    app.dependency_overrides[require_agent] = lambda: {"role": "agent", "agent_id": None}
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_agent, None)


@contextmanager
def _mock_admin():
    from app.main import app
    from app.core.auth import require_admin
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest_asyncio.fixture(scope="session")
async def rate_limit_setup():
    """Push updated base.rego to OPA, seed test agent, create rate_limit policy."""
    from app.models.database import async_session_factory
    from app.services.policy_loader import push_rego_to_opa

    # Push the worktree's updated base.rego (with rate_limit rules) to OPA
    await push_rego_to_opa()

    async with async_session_factory() as session:
        # Seed test agent with query_credit_bureau in approved_tools
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools)
            VALUES (:id, 'rate-test-agent', 'test@test.com', 'active',
                    '["query_credit_bureau"]'::jsonb)
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(RATE_TEST_AGENT_ID)})
        await session.commit()

    # Create rate_limit policy via API (so it gets a proper UUID we can assert on)
    from app.main import app
    with _mock_admin():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/policies", json={
                "name": RATE_POLICY_NAME,
                "description": "Test: deny > 10 credit queries per session",
                "rule_type": "rate_limit",
                "condition": {
                    "tools": [RATE_TOOL],
                    "rate_limit": {"max_calls": 10, "window": "session"},
                },
                "action": "deny",
                "active": True,
                "severity": "high",
                "compliance_tags": [],
            })
            assert resp.status_code == 201, resp.text
            policy_id = resp.json()["id"]

    yield {"policy_id": policy_id}

    # Teardown: remove test data
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM audit_events WHERE agent_id = :id"),
            {"id": str(RATE_TEST_AGENT_ID)},
        )
        await session.execute(
            text("DELETE FROM sessions WHERE agent_id = :id"),
            {"id": str(RATE_TEST_AGENT_ID)},
        )
        await session.execute(
            text("DELETE FROM agents WHERE id = :id"),
            {"id": str(RATE_TEST_AGENT_ID)},
        )
        await session.execute(
            text("DELETE FROM policies WHERE name = :name"),
            {"name": RATE_POLICY_NAME},
        )
        await session.commit()


async def _ensure_session(session_id: uuid.UUID) -> None:
    """Ensure a sessions row exists for the given session_id."""
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO sessions (id, agent_id, status)
            VALUES (:id, :agent_id, 'active')
            ON CONFLICT (id) DO NOTHING
        """), {"id": str(session_id), "agent_id": str(RATE_TEST_AGENT_ID)})
        await session.commit()


async def _seed_audit_events(session_id: uuid.UUID, count: int) -> None:
    """Insert count prior audit_events for RATE_TEST_AGENT_ID in the given session."""
    from app.models.database import async_session_factory

    await _ensure_session(session_id)

    async with async_session_factory() as session:
        for i in range(count):
            await session.execute(text("""
                INSERT INTO audit_events
                    (id, session_id, agent_id, agent_name, tool_name,
                     tool_parameters, decision, decision_reason, sequence_number)
                VALUES
                    (gen_random_uuid(), :session_id, :agent_id, 'rate-test-agent',
                     :tool_name, '{}'::jsonb, 'allow', 'default_allow', :seq)
            """), {
                "session_id": str(session_id),
                "agent_id": str(RATE_TEST_AGENT_ID),
                "tool_name": RATE_TOOL,
                "seq": i + 1,
            })
        await session.commit()


async def _clear_audit_events(session_id: uuid.UUID) -> None:
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM audit_events WHERE session_id = :sid"),
            {"sid": str(session_id)},
        )
        await session.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_call_11_denied_with_rate_limit_reason(rate_limit_setup):
    """Call 11 (count = 10 prior) must be denied with correct reason and policy_id."""
    from app.main import app

    await _seed_audit_events(RATE_TEST_SESSION_A, 10)
    try:
        with _mock_agent():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/intercept", json={
                    "session_id": str(RATE_TEST_SESSION_A),
                    "agent_id": str(RATE_TEST_AGENT_ID),
                    "agent_name": "rate-test-agent",
                    "tool_name": RATE_TOOL,
                    "tool_parameters": {"customer_id": "CUST-000011"},
                    "sequence_number": 11,
                })

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["decision"] == "deny"
        assert body["reason"].startswith("rate_limit_exceeded:query_credit_bureau:10:session")
        assert body["policy_id"] == rate_limit_setup["policy_id"]
        assert body["policy_name"] == RATE_POLICY_NAME
    finally:
        await _clear_audit_events(RATE_TEST_SESSION_A)


@pytest.mark.asyncio
async def test_call_10_allowed(rate_limit_setup):
    """Call 10 (count = 9 prior) must be allowed."""
    from app.main import app

    await _seed_audit_events(RATE_TEST_SESSION_A, 9)
    try:
        with _mock_agent():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/intercept", json={
                    "session_id": str(RATE_TEST_SESSION_A),
                    "agent_id": str(RATE_TEST_AGENT_ID),
                    "agent_name": "rate-test-agent",
                    "tool_name": RATE_TOOL,
                    "tool_parameters": {"customer_id": "CUST-000010"},
                    "sequence_number": 10,
                })

        assert resp.status_code == 200, resp.text
        assert resp.json()["decision"] == "allow"
    finally:
        await _clear_audit_events(RATE_TEST_SESSION_A)


@pytest.mark.asyncio
async def test_rate_limit_does_not_apply_cross_session(rate_limit_setup):
    """10 calls in session A should not cause denial in a fresh session B."""
    from app.main import app

    await _seed_audit_events(RATE_TEST_SESSION_A, 10)
    try:
        with _mock_agent():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/intercept", json={
                    "session_id": str(RATE_TEST_SESSION_B),
                    "agent_id": str(RATE_TEST_AGENT_ID),
                    "agent_name": "rate-test-agent",
                    "tool_name": RATE_TOOL,
                    "tool_parameters": {"customer_id": "CUST-000001"},
                    "sequence_number": 1,
                })

        assert resp.status_code == 200, resp.text
        assert resp.json()["decision"] == "allow"
    finally:
        await _clear_audit_events(RATE_TEST_SESSION_A)
