"""Integration tests: /auth/login, /auth/magic-link/validate, /setup/complete
must reject with 429 after repeated attempts from the same client IP."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.models.database import async_session_factory
from app.core.rate_limiter import reset_rate_limits


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


_USER_SELECT_SQL = (
    "SELECT id, email, name, role::text, is_active, last_login, created_at, "
    "password_hash, is_root, invite_token_hash, invite_expires_at, password_set "
    "FROM users"
)

_USER_INSERT_SQL = """
    INSERT INTO users (
        id, email, name, role, is_active, last_login, created_at,
        password_hash, is_root, invite_token_hash, invite_expires_at, password_set
    )
    VALUES (
        :id, :email, :name, CAST(:role AS userrole), :is_active, :last_login, :created_at,
        :password_hash, :is_root, :invite_token_hash, :invite_expires_at, :password_set
    )
    ON CONFLICT (email) DO NOTHING
"""


def _user_row_to_params(row):
    return {
        "id": str(row.id),
        "email": row.email,
        "name": row.name,
        "role": row.role,
        "is_active": row.is_active,
        "last_login": row.last_login,
        "created_at": row.created_at,
        "password_hash": row.password_hash,
        "is_root": row.is_root,
        "invite_token_hash": row.invite_token_hash,
        "invite_expires_at": row.invite_expires_at,
        "password_set": row.password_set,
    }


@pytest_asyncio.fixture(scope="session")
async def _isolated_setup_db():
    """Snapshot/clear users+org_settings for this test only, restore after --
    /setup/complete behaves differently depending on whether any user exists,
    so this test must not depend on or permanently mutate real DB state."""
    async with async_session_factory() as db:
        saved_users = (await db.execute(text(_USER_SELECT_SQL))).fetchall()
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(text("DELETE FROM users"))
        await db.commit()

    yield

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(text("DELETE FROM users"))
        for row in saved_users:
            await db.execute(text(_USER_INSERT_SQL), _user_row_to_params(row))
        await db.commit()


@pytest.mark.asyncio
async def test_login_rate_limited_after_repeated_attempts():
    transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for _ in range(10):
            resp = await c.post(
                "/auth/login",
                json={"email": "nobody-ratelimit@example.com", "password": "wrong"},
            )
            assert resp.status_code == 401
        resp = await c.post(
            "/auth/login",
            json={"email": "nobody-ratelimit@example.com", "password": "wrong"},
        )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_magic_link_rate_limited_after_repeated_attempts():
    transport = ASGITransport(app=app, client=("203.0.113.6", 12345))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for _ in range(10):
            resp = await c.post("/auth/magic-link/validate", json={"token": "not-a-real-token"})
            assert resp.status_code == 401
        resp = await c.post("/auth/magic-link/validate", json={"token": "not-a-real-token"})
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_setup_complete_rate_limited_after_repeated_attempts(_isolated_setup_db):
    transport = ASGITransport(app=app, client=("203.0.113.7", 12345))
    payload = {
        "full_name": "Rate Limit Test",
        "email": "ratelimit-setup@example.com",
        "password": "securepass123",
        "org_name": "Org",
        "timezone": "UTC",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        statuses = []
        for _ in range(10):
            resp = await c.post("/setup/complete", json=payload)
            statuses.append(resp.status_code)
        resp = await c.post("/setup/complete", json=payload)
    assert all(s != 429 for s in statuses)
    assert resp.status_code == 429
