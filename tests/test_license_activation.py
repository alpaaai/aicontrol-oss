"""Tests for PUT /settings/license-activation (plans/v4 task 23) -- the
only way an activation code enters an aicontrol instance (BillingPage.tsx
only, no install.sh prompt, per scope decision 4)."""
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.main import app
from app.models.database import async_session_factory
from app.services.billing_client import BillingClientError


@pytest_asyncio.fixture(scope="session")
async def _org_row():
    """Replace org_settings with a single known row; restore after.
    Session-scoped: matches tests/test_org_settings.py's own fixture --
    a function-scoped async DB fixture combined with AsyncClient hits this
    repo's known pytest-asyncio/asyncpg event-loop pitfall (see
    tests/conftest.py's own fixtures, which are all session-scoped for the
    same reason)."""
    async with async_session_factory() as db:
        saved = await db.execute(text("SELECT id, org_name, timezone FROM org_settings"))
        existing = saved.fetchall()
        await db.execute(text("DELETE FROM org_settings"))
        result = await db.execute(
            text("""
                INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at)
                VALUES (gen_random_uuid(), 'Task23 Test Org', 'America/New_York', now(), now())
                RETURNING id
            """)
        )
        row_id = str(result.scalar_one())
        await db.commit()
    yield {"id": row_id}
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


async def _reset_activation_fields(row_id):
    async with async_session_factory() as db:
        await db.execute(
            text("UPDATE org_settings SET activation_code = NULL, license_status = NULL, "
                 "license_plan = NULL, license_synced_at = NULL WHERE id = :id"),
            {"id": row_id},
        )
        await db.commit()


@pytest.mark.asyncio
async def test_valid_activation_code_saves_and_returns_license_status(_org_row, human_admin_token):
    await _reset_activation_fields(_org_row["id"])
    with patch(
        "app.routers.org_settings.sync_license",
        new_callable=AsyncMock,
        return_value={"status": "active", "plan": "business"},
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put(
                "/settings/license-activation",
                json={"activation_code": "valid-code"},
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["license_status"] == "active"
    assert body["license_plan"] == "business"
    assert body["license_synced_at"] is not None

    async with async_session_factory() as db:
        row = (await db.execute(text("SELECT activation_code, license_status, license_plan FROM org_settings"))).first()
    assert row.activation_code == "valid-code"
    assert row.license_status == "active"
    assert row.license_plan == "business"


@pytest.mark.asyncio
async def test_invalid_activation_code_returns_400_and_does_not_save(_org_row, human_admin_token):
    await _reset_activation_fields(_org_row["id"])
    with patch(
        "app.routers.org_settings.sync_license",
        new_callable=AsyncMock,
        side_effect=BillingClientError("billing-service returned 401"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put(
                "/settings/license-activation",
                json={"activation_code": "bad-code"},
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )

    assert resp.status_code == 400

    async with async_session_factory() as db:
        row = (await db.execute(text("SELECT activation_code FROM org_settings"))).first()
    assert row.activation_code is None


@pytest.mark.asyncio
async def test_non_admin_human_gets_403(_org_row, human_analyst_token):
    await _reset_activation_fields(_org_row["id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.put(
            "/settings/license-activation",
            json={"activation_code": "valid-code"},
            headers={"Authorization": f"Bearer {human_analyst_token}"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_requires_auth(_org_row):
    await _reset_activation_fields(_org_row["id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.put(
            "/settings/license-activation",
            json={"activation_code": "valid-code"},
        )
    assert resp.status_code in (401, 403)
