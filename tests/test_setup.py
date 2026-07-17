"""Tests for onboarding_identity migration and /setup endpoints."""
import pytest
import pytest_asyncio
from sqlalchemy import text
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.database import async_session_factory


# ── Schema verification (Task 1) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_users_table_has_new_columns():
    expected = {"password_hash", "is_root", "invite_token_hash", "invite_expires_at", "password_set"}
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = ANY(:cols)"
            ),
            {"cols": list(expected)},
        )
        found = {row[0] for row in result.fetchall()}
    assert found == expected, f"Missing columns: {expected - found}"


@pytest.mark.asyncio
async def test_org_settings_table_exists():
    expected = {"id", "org_name", "timezone", "created_at", "updated_at"}
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'org_settings'"
            )
        )
        found = {row[0] for row in result.fetchall()}
    assert found == expected, f"Unexpected org_settings columns: {found ^ expected}"


# ── Fixture: save/clear/restore users for setup behavioral tests ──────────────
#
# Restore must round-trip every column. An earlier version only saved
# (email, role, is_active), which silently dropped password_hash,
# password_set, is_root, and invite fields on restore -- wiping real user
# passwords every time the full test suite ran.

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


async def _snapshot_and_clear_users(db):
    """Save every user column, then wipe users + org_settings. Returns saved rows."""
    result = await db.execute(text(_USER_SELECT_SQL))
    saved_users = result.fetchall()
    await db.execute(text("DELETE FROM org_settings"))
    await db.execute(text("DELETE FROM users"))
    return saved_users


async def _restore_users(db, saved_users):
    """Wipe users + org_settings, then reinsert saved rows with all columns intact."""
    await db.execute(text("DELETE FROM org_settings"))
    await db.execute(text("DELETE FROM users"))
    for row in saved_users:
        await db.execute(text(_USER_INSERT_SQL), _user_row_to_params(row))


@pytest_asyncio.fixture(scope="session")
async def _setup_db_clean():
    """Clear users + org_settings before setup behavioral tests, restore after."""
    async with async_session_factory() as db:
        saved_users = await _snapshot_and_clear_users(db)
        await db.commit()

    yield

    async with async_session_factory() as db:
        await _restore_users(db, saved_users)
        await db.commit()


@pytest.mark.asyncio
async def test_setup_db_clean_preserves_all_user_fields():
    """Regression test: snapshot/restore must not drop password_hash,
    password_set, is_root, or invite fields."""
    email = "regression_snap@example.com"
    async with async_session_factory() as db:
        await db.execute(
            text("""
                INSERT INTO users (
                    id, email, name, role, is_active, password_hash, is_root,
                    password_set, invite_token_hash, invite_expires_at, created_at
                ) VALUES (
                    gen_random_uuid(), :email, 'Snap Test', 'admin', true,
                    'hashed-secret', true, true, 'invite-hash', now(), now()
                )
            """),
            {"email": email},
        )
        await db.commit()

    try:
        async with async_session_factory() as db:
            saved = await _snapshot_and_clear_users(db)
            await db.commit()

        async with async_session_factory() as db:
            await _restore_users(db, saved)
            await db.commit()

        async with async_session_factory() as db:
            result = await db.execute(
                text(
                    "SELECT password_hash, is_root, password_set, invite_token_hash "
                    "FROM users WHERE email = :email"
                ),
                {"email": email},
            )
            row = result.fetchone()

        assert row is not None, "user row lost during snapshot/restore"
        assert row.password_hash == "hashed-secret"
        assert row.is_root is True
        assert row.password_set is True
        assert row.invite_token_hash == "invite-hash"
    finally:
        async with async_session_factory() as db:
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
            await db.commit()


_SETUP_PAYLOAD = {
    "full_name": "Root Admin",
    "email": "root@example.com",
    "password": "securepass123",
    "org_name": "Test Org",
    "timezone": "America/New_York",
}


# ── /setup/status & /setup/complete behavioral tests ─────────────────────────

@pytest.mark.asyncio
async def test_setup_status_required(_setup_db_clean):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/setup/status")
    assert resp.status_code == 200
    assert resp.json() == {"setup_required": True}


@pytest.mark.asyncio
async def test_setup_complete_success(_setup_db_clean):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/setup/complete", json=_SETUP_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["user"]["email"] == _SETUP_PAYLOAD["email"]
    assert body["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_setup_status_not_required(_setup_db_clean):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/setup/status")
    assert resp.status_code == 200
    assert resp.json() == {"setup_required": False}


@pytest.mark.asyncio
async def test_setup_complete_409_if_users_exist(_setup_db_clean):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/setup/complete", json=_SETUP_PAYLOAD)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_setup_complete_short_password():
    payload = {**_SETUP_PAYLOAD, "password": "short"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/setup/complete", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_setup_complete_invalid_timezone():
    payload = {**_SETUP_PAYLOAD, "timezone": "Not/A_Timezone"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/setup/complete", json=payload)
    assert resp.status_code == 422
