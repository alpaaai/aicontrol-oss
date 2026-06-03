"""Tests for GET /org-settings and PUT /org-settings."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.models.database import async_session_factory


@pytest_asyncio.fixture(scope="session")
async def _org_row():
    """Replace org_settings with a single known row; restore after."""
    async with async_session_factory() as db:
        saved = await db.execute(text("SELECT id, org_name, timezone FROM org_settings"))
        existing = saved.fetchall()
        await db.execute(text("DELETE FROM org_settings"))
        result = await db.execute(
            text("""
                INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at)
                VALUES (gen_random_uuid(), 'Test Org', 'America/New_York', now(), now())
                RETURNING id
            """)
        )
        row_id = str(result.scalar_one())
        await db.commit()
    yield {"id": row_id, "org_name": "Test Org", "timezone": "America/New_York"}
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM org_settings"))
        for row in existing:
            await db.execute(
                text("""
                    INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at)
                    VALUES (:id, :name, :tz, now(), now())
                    ON CONFLICT DO NOTHING
                """),
                {"id": str(row[0]), "name": row[1], "tz": row[2]},
            )
        await db.commit()


# ── GET /org-settings ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_org_settings_returns_200(_org_row, human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(
            "/org-settings",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["org_name"] == "Test Org"
    assert body["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_get_org_settings_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/org-settings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_org_settings_404_when_not_set_up(human_admin_token):
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM org_settings"))
        await db.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                "/org-settings",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
        assert resp.status_code == 404
    finally:
        async with async_session_factory() as db:
            await db.execute(
                text("""
                    INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at)
                    VALUES (gen_random_uuid(), 'Test Org', 'America/New_York', now(), now())
                """)
            )
            await db.commit()


# ── PUT /org-settings ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_put_org_settings_updates_name_and_timezone(_org_row, human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.put(
            "/org-settings",
            json={"org_name": "Updated Org", "timezone": "Europe/London"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["org_name"] == "Updated Org"
    assert body["timezone"] == "Europe/London"


@pytest.mark.asyncio
async def test_put_org_settings_rejects_invalid_timezone(_org_row, human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.put(
            "/org-settings",
            json={"org_name": "X", "timezone": "Not/ATimezone"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_org_settings_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.put("/org-settings", json={"org_name": "X", "timezone": "UTC"})
    assert resp.status_code == 401
