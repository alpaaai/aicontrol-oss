"""Shared pytest fixtures."""
import base64
import importlib
import json
import os
import time
import uuid
import pytest
import pytest_asyncio
from unittest.mock import patch
import httpx
from sqlalchemy import text

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


@pytest.fixture(autouse=True)
def reset_config_and_db_engine():
    """
    Reload app.core.config and reset the dashboard engine cache after each test.

    test_config.py reloads app.core.config with a fake DATABASE_URL, leaving
    the module-level settings singleton poisoned for subsequent tests. This
    fixture restores the real settings and clears the cached sync engine so
    the next test gets a fresh connection with the correct URL.
    """
    yield
    import app.core.config
    importlib.reload(app.core.config)

    import dashboard.db
    dashboard.db._sync_engine = None
    dashboard.db._SyncSession = None


# ── Integration test fixtures (live API at localhost:8001) ────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_policies():
    """Session setup + teardown: remove test_ and not_lib_ policies so they don't
    accumulate across pytest runs. Runs cleanup both before and after."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await session.execute(text(
            "UPDATE audit_events SET policy_id = NULL, policy_name = NULL "
            "WHERE policy_id IN (SELECT id FROM policies WHERE name LIKE 'test_%' OR name LIKE 'not_lib_%')"
        ))
        await session.execute(text("DELETE FROM policies WHERE name LIKE 'test_%' OR name LIKE 'not_lib_%'"))
        await session.commit()
    yield
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await session.execute(text(
            "UPDATE audit_events SET policy_id = NULL, policy_name = NULL "
            "WHERE policy_id IN (SELECT id FROM policies WHERE name LIKE 'test_%' OR name LIKE 'not_lib_%')"
        ))
        await session.execute(text("DELETE FROM policies WHERE name LIKE 'test_%' OR name LIKE 'not_lib_%'"))
        await session.commit()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_agents():
    """Session setup + teardown: remove test-agent-* rows so they don't accumulate
    across pytest runs. Runs cleanup both before (removes prior-run leaks) and
    after (removes this-run creations)."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM agents WHERE name LIKE 'test-agent-%'"))
        await session.commit()
    yield
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM agents WHERE name LIKE 'test-agent-%'"))
        await session.commit()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_admission_scans():
    """Session setup + teardown: remove admission_scans rows created by
    test_admission_scans_api.py (target_ref='/some/skill') so they don't
    accumulate across pytest runs."""
    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM admission_scans WHERE target_ref = '/some/skill'"))
        await session.commit()
    yield
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM admission_scans WHERE target_ref = '/some/skill'"))
        await session.commit()


@pytest_asyncio.fixture(scope="session")
async def _seed_and_token_setup():
    """Session-scoped: seed demo agents + issue admin and agent tokens once."""
    from app.core.auth import create_token, hash_token
    from app.models.database import async_session_factory
    from scripts.seed import AGENTS

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


@pytest_asyncio.fixture(scope="session")
async def seed_admin_user():
    """Ensure admin@aicontrol.dev exists in users table for OTP auth tests."""
    from app.models.database import async_session_factory
    from app.models.user import User, UserRole
    from sqlalchemy import select
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.email == "admin@aicontrol.dev")
        )
        if not result.scalar_one_or_none():
            session.add(User(email="admin@aicontrol.dev", role=UserRole.admin, name="Admin"))
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
            INSERT INTO policies (id, name, rule_type, condition, action, active)
            VALUES (:id, 'test_p1_8a_policy', 'tool_call', '{"tool": "any"}'::jsonb, 'allow', true)
        """), {"id": str(policy_id)})
        await db.commit()

    yield policy_id

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM policies WHERE id = :id"), {"id": str(policy_id)})
        await db.commit()


# ── License test fixtures ─────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_test_jwt(private_key, plan: str, iss: str = "aictl.io",
                   days: int = 365, company: str = "Test Corp") -> str:
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes

    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": iss,
        "jti": str(uuid.uuid4()),
        "company": company,
        "email": "admin@test.com",
        "plan": plan,
        "issued_at": int(time.time()),
        "exp": int(time.time()) + days * 86400,
    }
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig_input = f"{h}.{p}".encode()
    sig = private_key.sign(sig_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{h}.{p}.{_b64url(sig)}"


@pytest.fixture(scope="session")
def test_rsa_keypair():
    """Generate a fresh RSA keypair for test use only."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_key, public_pem


@pytest.fixture(scope="session")
def valid_enterprise_token(test_rsa_keypair):
    private_key, _ = test_rsa_keypair
    return _make_test_jwt(private_key, "enterprise")


@pytest.fixture(scope="session")
def valid_business_token(test_rsa_keypair):
    private_key, _ = test_rsa_keypair
    return _make_test_jwt(private_key, "business")


@pytest.fixture(scope="session")
def expired_enterprise_token(test_rsa_keypair):
    private_key, _ = test_rsa_keypair
    return _make_test_jwt(private_key, "enterprise", days=-1)


@pytest.fixture
def patch_license_public_key(test_rsa_keypair):
    """Patch PUBLIC_KEY so decode_license_key uses the test keypair."""
    _, public_pem = test_rsa_keypair
    with patch("app.core.license.PUBLIC_KEY", public_pem):
        yield
