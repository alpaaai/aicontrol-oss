"""Shared pytest fixtures."""
import importlib
import os
import uuid
import pytest
import pytest_asyncio
from unittest.mock import patch
import httpx
from sqlalchemy import text

from scripts import db_hygiene

# Demo agent fixture data, copied from scripts/seed.py (which is gitignored --
# demo-only, not shipped). Kept here so core test infra doesn't depend on a
# file that may be absent on a fresh clone or in CI.
AGENTS = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "claims-processing-agent",
        "owner": "ai-team@acme-insurance.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000010",
        "name": "loan-underwriting-agent",
        "owner": "lending-team@bank.com",
        "status": "active",
        "tools": '["query_credit_bureau", "run_risk_model"]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000020",
        "name": "clinical-documentation-agent",
        "owner": "clinical-ops@hospital.org",
        "status": "active",
        "tools": '["read_patient_record", "query_lab_results"]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000030",
        "name": "incident-response-agent",
        "owner": "platform-ops@company.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000040",
        "name": "supplier-sourcing-agent",
        "owner": "procurement@manufacturer.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000050",
        "name": "support-resolution-agent",
        "owner": "cx-platform@company.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000060",
        "name": "crm-automation-agent",
        "owner": "revops@company.com",
        "status": "active",
        "tools": '[]',
    },
    {
        "id": "00000000-0000-0000-0000-000000000070",
        "name": "insurance-claims-agent",
        "owner": "claims-ops@insurer.com",
        "status": "active",
        "tools": '[]',
    },
]

AGENT_APPROVED_TOOLS = {
    "00000000-0000-0000-0000-000000000010": [
        "query_credit_bureau",
        "run_risk_model",
        "get_income_verification",
        "get_employment_history",
        "approve_loan",
        "deny_loan",
    ],
    "00000000-0000-0000-0000-000000000020": [
        "read_patient_record",
        "write_soap_note",
        "get_lab_results",
        "get_medication_list",
        "schedule_followup",
    ],
    "00000000-0000-0000-0000-000000000030": [
        "get_incident_details",
        "update_incident_status",
        "assign_ticket",
        "get_runbook",
        "restart_service",
        "send_notification",
    ],
    "00000000-0000-0000-0000-000000000040": [
        "query_inventory_system",
        "query_approved_supplier_catalog",
        "create_purchase_order",
        "get_supplier_quote",
    ],
    "00000000-0000-0000-0000-000000000050": [
        "read_customer_account",
        "update_ticket_status",
        "send_email",
        "create_refund",
        "escalate_ticket",
    ],
    "00000000-0000-0000-0000-000000000060": [
        "update_deal_stage",
        "log_sales_activity",
        "get_account_details",
        "create_task",
        "send_follow_up",
    ],
    "00000000-0000-0000-0000-000000000070": [
        "get_claim_details",
        "validate_policy_coverage",
        "process_claim_payment",
        "request_additional_info",
        "flag_for_review",
    ],
}

# When tests run on the host machine, Docker internal hostnames won't resolve.
# Load .env (if present) and replace Docker internal hostnames with localhost.
try:
    from dotenv import load_dotenv, dotenv_values
    # Walk up from tests/ to find .env (handles git worktrees where .env lives in the main repo root)
    _start = os.path.dirname(os.path.abspath(__file__))
    _env_file = None
    _search = _start
    for _ in range(5):
        _candidate = os.path.join(_search, ".env")
        if os.path.isfile(_candidate):
            _env_file = _candidate
            break
        _search = os.path.dirname(_search)
    if _env_file:
        load_dotenv(_env_file, override=False)  # populate os.environ without overriding explicit env vars
    _db = os.environ.get("DATABASE_URL", "")
    if "@postgres:" in _db:
        os.environ["DATABASE_URL"] = _db.replace("@postgres:", "@localhost:")
    _opa = os.environ.get("OPA_URL", "")
    if _opa == "http://opa:8181":
        os.environ["OPA_URL"] = "http://localhost:8181"
    _slack = os.environ.get("SLACK_BOT_TOKEN", "")
    if not _slack or _slack == "xoxb-placeholder":
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test-token"
except Exception:
    pass  # dotenv not available or .env not found — rely on existing env

# Tests must never share a WAL directory with a live dev server (e.g. one
# started manually via `uvicorn app.main:app --reload` for local testing).
# Both processes bind app.services.wal.default_wal_writer to the same file
# path by default, and pytest fixtures that call WalWriter.reset_for_tests()
# unlink that file + its checkpoint out from under the live server: the
# server's in-memory _next_seq doesn't reset, so its next append restarts
# the recreated file's wal_seq numbering below the shipper's stale
# in-memory checkpoint, permanently orphaning those entries — they're
# silently never shipped to Postgres. Set before any app.* import so the
# module-level default_wal_writer singleton binds to an isolated path.
os.environ["WAL_DIR"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".pytest_wal"
)

# DEMO_MODE defaults to false (3.1 fix: a real deployment must opt in to the
# unauthenticated /demo/* endpoints). This line does NOT make the demo tests
# pass by itself: the shared `client` fixture below talks over real HTTP to
# whatever process is already listening on AICONTROL_TEST_BASE_URL /
# localhost:8001 (see `client` fixture) -- it never imports app.main or
# constructs the FastAPI app in this pytest process. Setting os.environ here
# only affects in-process app construction (e.g. tests that build their own
# ASGITransport(app=...), like test_health_endpoint.py), not that external
# server. For test_demo_router.py / test_demo_scenario_decisions.py /
# the /demo/call_tool tests in test_agents_coverage_response.py to pass, the
# dev server itself must be started with DEMO_MODE=true in ITS environment
# (`DEMO_MODE=true uvicorn app.main:app --reload --port 8001`) -- otherwise
# every one of those tests 404s with no indication why. See
# `_require_demo_mode_on_server` fixture below, which fails fast with that
# explanation instead of letting it surface as a bare 404.
os.environ["DEMO_MODE"] = "true"


@pytest_asyncio.fixture(scope="session")
async def _require_demo_mode_on_server():
    """Fail fast with an actionable message if the live server under test
    doesn't have DEMO_MODE=true, instead of letting every /demo/* test in
    the module fail with an unexplained 404 Not Found."""
    base_url = os.environ.get("AICONTROL_TEST_BASE_URL", "http://localhost:8001")
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as c:
        resp = await c.get("/demo/status")
    if resp.status_code == 404:
        pytest.fail(
            f"{base_url}/demo/status returned 404 -- the server under test "
            "was not started with DEMO_MODE=true. Restart it with "
            "`DEMO_MODE=true uvicorn app.main:app --reload --port 8001` "
            "before running these tests.",
            pytrace=False,
        )


@pytest.fixture(autouse=True)
def reset_config_and_db_engine():
    """
    Reload app.core.config after each test.

    test_config.py reloads app.core.config with a fake DATABASE_URL, leaving
    the module-level settings singleton poisoned for subsequent tests. This
    fixture restores the real settings and clears the cached sync engine so
    the next test gets a fresh connection with the correct URL.
    """
    yield
    import app.core.config
    importlib.reload(app.core.config)



@pytest_asyncio.fixture(loop_scope="session")
async def db_session():
    """An async ORM session that never commits. Tests flush to exercise the
    schema, then the rollback on teardown discards everything -- no cleanup
    fixture needed for rows created through this."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


# ── Integration test fixtures (live API at localhost:8001) ────────────────────



# The agents/policies/discovery sweeps below all delegate to scripts/db_hygiene.py
# -- the single source of truth for what a leaked test row looks like and how to
# clean it, shared with the standalone db_hygiene_check.py CLI. Each wrapper here
# exists only to keep the pre-existing import paths that test_conftest_*_cleanup.py
# regression tests rely on; the logic itself lives in db_hygiene.py.

@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_policies():
    """Session setup + teardown: remove test_ and not_lib_ policies so they don't
    accumulate across pytest runs. Runs cleanup both before and after."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await db_hygiene._clean_policies(session)
        await session.commit()
    yield
    async with async_session_factory() as session:
        await db_hygiene._clean_policies(session)
        await session.commit()


async def _cleanup_test_agent_rows(session):
    # sessions.agent_id, audit_events.agent_id and audit_events.session_id are
    # all NO ACTION FKs, so a bare DELETE FROM agents raises
    # ForeignKeyViolationError the moment a test drives a real intercept for a
    # test agent -- which aborts this session-scoped fixture and turns every
    # later test into an "ERROR at setup". See db_hygiene._clean_agents for
    # the full FK-safe ordering.
    await db_hygiene._clean_agents(session)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_agents():
    """Session setup + teardown: remove test-* agent rows so they don't accumulate
    across pytest runs. Runs cleanup both before (removes prior-run leaks) and
    after (removes this-run creations)."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await _cleanup_test_agent_rows(session)
        await session.commit()
    yield
    async with async_session_factory() as session:
        await _cleanup_test_agent_rows(session)
        await session.commit()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_mcp_servers():
    """Session setup + teardown: remove test-mcp-server-* rows so they don't
    accumulate across pytest runs. test_mcp_servers_router.py creates these
    inline with no cleanup of its own -- same class of gap the agents/
    policies/discovery sweeps above already cover, just never extended here;
    confirmed leaking via `python scripts/db_hygiene_check.py` after a plain
    `pytest tests/` run (mcp_servers: 4, user_activity_log: 5 referencing
    them) with no other test having touched either table that session."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await db_hygiene._clean_mcp_servers(session)
        await session.commit()
    yield
    async with async_session_factory() as session:
        await db_hygiene._clean_mcp_servers(session)
        await session.commit()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_activity_log():
    """Session setup + teardown: remove user_activity_log rows referencing
    test-agent-*/test-mcp-server-*/test_*/not_lib_* data (db_hygiene.py's
    _clean_activity_log) so they don't accumulate across pytest runs. Same
    gap as _cleanup_test_mcp_servers above -- db_hygiene.py already defines
    the sweep, nothing in this file was calling it automatically."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await db_hygiene._clean_activity_log(session)
        await session.commit()
    yield
    async with async_session_factory() as session:
        await db_hygiene._clean_activity_log(session)
        await session.commit()


async def _cleanup_test_discovery_rows(session):
    # Agents promoted from a discovery row are covered by the 'test-%' agents
    # sweep above; this only needs to clear discovered_agents itself.
    await db_hygiene._clean_discovery(session)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_discovery():
    """Session setup + teardown: remove discovered_agents rows
    created by tests/enterprise/test_discovery_api.py so they don't
    accumulate across pytest runs. Same class of bug fixed in fc54acd
    (test_promote_creates_a_real_agent had no cleanup fixture, so an
    assertion failure before its own inline cleanup ran left a leaked row
    permanently) -- following the established
    _cleanup_test_agents/_cleanup_test_policies pattern: runs both before
    (removes prior-run leaks) and after (removes this-run creations)
    regardless of test outcome, rather than relying on inline
    post-assertion cleanup in each test."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await _cleanup_test_discovery_rows(session)
        await session.commit()
    yield
    async with async_session_factory() as session:
        await _cleanup_test_discovery_rows(session)
        await session.commit()


_PYTEST_FIXTURE_TOKEN_DESCRIPTIONS = ("pytest-admin-fixture", "pytest-agent-fixture")

# Throwaway descriptions used only by test_conftest_token_cleanup.py to exercise
# the deletion helper. Kept disjoint from the real ones above so that test can
# never delete the live tokens _seed_and_token_setup issued for this session.
_PROBE_TOKEN_DESCRIPTIONS = ("pytest-probe-admin-token", "pytest-probe-agent-token")


async def _delete_pytest_fixture_tokens(session, descriptions=None):
    """Delete api_tokens rows by description. Defaults to the live fixture
    descriptions; callers that only want to exercise the mechanism must pass
    their own throwaway descriptions."""
    descs = _PYTEST_FIXTURE_TOKEN_DESCRIPTIONS if descriptions is None else descriptions
    await session.execute(
        text("DELETE FROM api_tokens WHERE description = ANY(:descs)"),
        {"descs": list(descs)},
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_pytest_fixture_tokens():
    """Session setup + teardown: remove pytest-*-fixture api_tokens rows so they
    don't accumulate across pytest runs. Runs cleanup both before (removes
    prior-run leaks) and after (removes this-run creations)."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await _delete_pytest_fixture_tokens(session)
        await _delete_pytest_fixture_tokens(session, descriptions=_PROBE_TOKEN_DESCRIPTIONS)
        await session.commit()
    yield
    async with async_session_factory() as session:
        await _delete_pytest_fixture_tokens(session)
        await _delete_pytest_fixture_tokens(session, descriptions=_PROBE_TOKEN_DESCRIPTIONS)
        await session.commit()


@pytest_asyncio.fixture(scope="session")
async def _seed_and_token_setup():
    """Session-scoped: seed demo agents + issue admin and agent tokens once."""
    from app.core.auth import create_token, hash_token
    from app.models.database import async_session_factory

    async with async_session_factory() as session:
        # Seed demo agents (idempotent)
        for agent in AGENTS:
            await session.execute(text("""
                INSERT INTO agents (id, name, owner, status, approved_tools)
                VALUES (:id, :name, :owner, :status, CAST(:tools AS jsonb))
                ON CONFLICT (id) DO UPDATE SET approved_tools = EXCLUDED.approved_tools
            """), agent)

        # Issue admin token
        admin_tok = create_token(role="admin", description="pytest-admin-fixture")
        await session.execute(text("""
            INSERT INTO api_tokens (id, token_hash, role, description, revoked)
            VALUES (gen_random_uuid(), :hash, 'admin', 'pytest-admin-fixture', false)
        """), {"hash": hash_token(admin_tok)})

        # Issue unscoped agent token (no agent_id FK so any agent_id is accepted)
        agent_tok = create_token(role="agent", description="pytest-agent-fixture")
        await session.execute(text("""
            INSERT INTO api_tokens (id, token_hash, role, description, revoked)
            VALUES (gen_random_uuid(), :hash, 'agent', 'pytest-agent-fixture', false)
        """), {"hash": hash_token(agent_tok)})

        await session.commit()

    return {"admin": admin_tok, "agent": agent_tok}


@pytest_asyncio.fixture
async def client(_seed_and_token_setup):
    base_url = os.environ.get("AICONTROL_TEST_BASE_URL", "http://localhost:8001")
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as c:
        yield c


@pytest.fixture
def admin_token(_seed_and_token_setup):
    return {"Authorization": f"Bearer {_seed_and_token_setup['admin']}"}


@pytest.fixture
def agent_token(_seed_and_token_setup):
    return {"Authorization": f"Bearer {_seed_and_token_setup['agent']}"}


@pytest_asyncio.fixture(scope="session")
async def _gateway_agent_setup():
    """Session-scoped: register a real test agent and issue a token scoped to
    it (api_tokens.agent_id set). require_gateway_agent (app/core/auth.py)
    rejects _seed_and_token_setup's agent token because that one is
    deliberately unscoped (agent_id NULL, so /intercept's require_agent
    accepts any client-supplied agent_id) -- the gateway has no such
    client-supplied field to scope from, so it needs a token whose agent_id
    FK is real. Session-scoped and deliberately never combined with a
    function-scoped async DB fixture in the same test (see test_mcp_gateway.py
    -- combining a session-scoped async fixture with a function-scoped one,
    e.g. db_session, crashes on asyncpg connection teardown with "attached to
    a different loop" in this stack; every fixture that touches the DB for
    gateway tests is session-scoped to avoid it). Cleanup rides on
    _cleanup_test_agents's existing test-agent-% sweep, which removes this
    row's api_tokens too (see scripts/db_hygiene._clean_agents's FK-safe
    ordering)."""
    from app.core.auth import create_token, hash_token
    from app.models.database import async_session_factory

    agent_id = uuid.uuid4()
    async with async_session_factory() as session:
        # governance_mode is explicit ('govern'), not left to the DB's
        # observe_by_default server_default -- these gateway tests exercise
        # real enforcement (deny/review), which observe mode would silently
        # collapse to allow (app/services/governance_engine.py's
        # evaluate_and_enforce).
        await session.execute(text("""
            INSERT INTO agents (id, name, owner, status, approved_tools, governance_mode)
            VALUES (:id, 'test-agent-mcp-gateway', 'pytest', 'active', '[]'::jsonb, 'govern')
        """), {"id": str(agent_id)})

        token = create_token(role="agent", description="pytest-gateway-agent-fixture")
        await session.execute(text("""
            INSERT INTO api_tokens (id, token_hash, role, description, revoked, agent_id)
            VALUES (gen_random_uuid(), :hash, 'agent', 'pytest-gateway-agent-fixture', false, :agent_id)
        """), {"hash": hash_token(token), "agent_id": str(agent_id)})
        await session.commit()

    return {"agent_id": str(agent_id), "token": token}


@pytest.fixture
def gateway_agent_token(_gateway_agent_setup):
    return {"Authorization": f"Bearer {_gateway_agent_setup['token']}"}


# ── P1-8a: human JWT + dashboard fixtures ────────────────────────────────────

@pytest.fixture
def human_admin_token():
    """Human JWT signed with the app secret — no DB lookup (require_human is signature-only)."""
    from datetime import datetime, timedelta
    from jose import jwt
    from app.core.config import settings
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "test_human@aicontrol.dev",
        "role": "admin",
        "type": "human",
        "exp": datetime.utcnow() + timedelta(hours=8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


@pytest.fixture
def human_analyst_token():
    """Non-admin human JWT — for asserting admin-only endpoints reject it."""
    from datetime import datetime, timedelta
    from jose import jwt
    from app.core.config import settings
    payload = {
        "sub": "00000000-0000-0000-0000-000000000002",
        "email": "test_analyst@aicontrol.dev",
        "role": "analyst",
        "type": "human",
        "exp": datetime.utcnow() + timedelta(hours=8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


async def _ensure_admin_user(session):
    """Insert admin@aicontrol.dev if missing. Returns True if this call created it."""
    from app.models.user import User, UserRole
    from sqlalchemy import select
    result = await session.execute(
        select(User).where(User.email == "admin@aicontrol.dev")
    )
    if result.scalar_one_or_none():
        return False
    session.add(User(email="admin@aicontrol.dev", role=UserRole.admin, name="Admin"))
    await session.commit()
    return True


async def _remove_admin_user_if_created(session, created):
    if created:
        await session.execute(text("DELETE FROM users WHERE email = 'admin@aicontrol.dev'"))


@pytest_asyncio.fixture(scope="session")
async def seed_admin_user():
    """Ensure admin@aicontrol.dev exists in users table for OTP auth tests.
    Removes the row on teardown if this fixture is the one that created it,
    so it doesn't linger as permanent test data."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        created = await _ensure_admin_user(session)

    yield

    async with async_session_factory() as session:
        await _remove_admin_user_if_created(session, created)
        await session.commit()


@pytest_asyncio.fixture(scope="session")
async def seed_audit_events():
    """Seed audit events with mixed decisions for filter tests."""
    import uuid
    from app.models.database import async_session_factory
    from sqlalchemy import text

    session_id = uuid.uuid4()
    event_ids = []
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO sessions (id, agent_id, started_at)
            VALUES (:sid, (SELECT id FROM agents LIMIT 1), NOW())
        """), {"sid": str(session_id)})
        for seq, decision in enumerate(["allow", "allow", "deny", "deny", "review"], 1):
            eid = uuid.uuid4()
            event_ids.append(eid)
            await db.execute(text("""
                INSERT INTO audit_events (id, session_id, sequence_number, tool_name, decision, created_at)
                VALUES (:id, :sid, :seq, 'test_filter_tool', :decision, NOW())
            """), {"id": str(eid), "sid": str(session_id), "seq": seq, "decision": decision})
        await db.commit()

    yield event_ids

    async with async_session_factory() as db:
        for eid in event_ids:
            await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
        await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(session_id)})
        await db.commit()


@pytest_asyncio.fixture(scope="session")
async def seed_sessions():
    """Seed two sessions with events. Returns list of session UUIDs."""
    import uuid
    from app.models.database import async_session_factory
    from sqlalchemy import text

    session_ids = [uuid.uuid4(), uuid.uuid4()]
    event_ids = []
    async with async_session_factory() as db:
        for sid in session_ids:
            await db.execute(text("""
                INSERT INTO sessions (id, agent_id, started_at)
                VALUES (:sid, (SELECT id FROM agents LIMIT 1), NOW())
            """), {"sid": str(sid)})
            eid = uuid.uuid4()
            event_ids.append(eid)
            await db.execute(text("""
                INSERT INTO audit_events (id, session_id, sequence_number, tool_name, decision, created_at)
                VALUES (:id, :sid, 1, 'test_tool', 'allow', NOW())
            """), {"id": str(eid), "sid": str(sid)})
        await db.commit()

    yield session_ids

    async with async_session_factory() as db:
        for eid in event_ids:
            await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(eid)})
        for sid in session_ids:
            await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(sid)})
        await db.commit()


@pytest_asyncio.fixture(scope="session")
async def seed_pending_review():
    """Seed a pending HITLReview and return its UUID."""
    import uuid
    from app.models.database import async_session_factory
    from sqlalchemy import text

    review_id = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO hitl_reviews (id, status, created_at)
            VALUES (:id, 'pending', NOW())
        """), {"id": str(review_id)})
        await db.commit()

    yield review_id

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM hitl_reviews WHERE id = :id"), {"id": str(review_id)})
        await db.commit()


@pytest_asyncio.fixture(scope="session")
async def seed_policy():
    """Seed a test policy and return its UUID."""
    import uuid
    from app.models.database import async_session_factory
    from sqlalchemy import text

    policy_id = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO policies (id, name, condition, effect, action_tool, active)
            VALUES (:id, 'test_p1_8a_policy', '{}'::jsonb, 'deny', 'any_tool', true)
        """), {"id": str(policy_id)})
        await db.commit()

    yield policy_id

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM policies WHERE id = :id"), {"id": str(policy_id)})
        await db.commit()
