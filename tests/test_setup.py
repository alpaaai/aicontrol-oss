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

@pytest_asyncio.fixture(scope="session")
async def _setup_db_clean():
    """Clear users + org_settings before setup behavioral tests, restore after."""
    async with async_session_factory() as db:
        result = await db.execute(text("SELECT email, role::text, is_active FROM users"))
        saved_users = result.fetchall()
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(text("DELETE FROM users"))
        await db.commit()

    yield

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(text("DELETE FROM users"))
        for email, role, is_active in saved_users:
            await db.execute(
                text("""
                    INSERT INTO users (id, email, role, is_active, created_at)
                    VALUES (gen_random_uuid(), :email, CAST(:role AS userrole), :active, now())
                    ON CONFLICT (email) DO NOTHING
                """),
                {"email": email, "role": role, "active": is_active},
            )
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
