"""Tests for PUT /settings/license-activation -- the only way a license
code enters an aicontrol instance (BillingPage.tsx only). Since plans/v5
2026-10-26-signed-license-keys the code is a signed license code verified
locally; billing-service is never called."""
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.main import app
from app.models.database import async_session_factory
from tests.conftest import restore_org_settings, snapshot_org_settings


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def _org_row():
    """Replace org_settings with a single known row; restore after.
    Session-scoped: matches tests/test_org_settings.py's own fixture --
    a function-scoped async DB fixture combined with AsyncClient hits this
    repo's known pytest-asyncio/asyncpg event-loop pitfall (see
    tests/conftest.py's own fixtures, which are all session-scoped for the
    same reason)."""
    async with async_session_factory() as db:
        existing = await snapshot_org_settings(db)
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
        await restore_org_settings(db, existing)
        await db.commit()


async def _reset_activation_fields(row_id):
    async with async_session_factory() as db:
        await db.execute(
            text("UPDATE org_settings SET activation_code = NULL, license_status = NULL, "
                 "license_plan = NULL, license_synced_at = NULL, license_key = NULL WHERE id = :id"),
            {"id": row_id},
        )
        await db.commit()


async def _activate(token, code):
    with patch("app.services.license_sync.LicenseSync.start") as mock_sync_start:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put(
                "/settings/license-activation",
                json={"activation_code": code},
                headers={"Authorization": f"Bearer {token}"},
            )
    mock_sync_start.assert_not_called()
    return resp


async def _license_row():
    async with async_session_factory() as db:
        return (await db.execute(text("SELECT license_key, activation_code FROM org_settings"))).first()


@pytest.mark.asyncio
async def test_valid_signed_code_is_stored_and_returns_its_plan(_org_row, human_admin_token, license_code):
    await _reset_activation_fields(_org_row["id"])
    code = license_code("business")
    resp = await _activate(human_admin_token, code)

    assert resp.status_code == 200
    body = resp.json()
    assert body["license_status"] == "active"
    assert body["license_plan"] == "business"
    assert body["license_synced_at"] is not None
    row = await _license_row()
    assert row.license_key == code
    assert row.activation_code is None


@pytest.mark.asyncio
async def test_activation_replaces_previous_code_and_clears_activation_code(_org_row, human_admin_token, license_code):
    await _reset_activation_fields(_org_row["id"])
    async with async_session_factory() as db:
        await db.execute(
            text("UPDATE org_settings SET license_key = :k, activation_code = 'old-billing-code' WHERE id = :id"),
            {"k": license_code("trial"), "id": _org_row["id"]},
        )
        await db.commit()
    upgrade = license_code("business")
    resp = await _activate(human_admin_token, upgrade)

    assert resp.status_code == 200
    assert resp.json()["license_plan"] == "business"
    row = await _license_row()
    assert row.license_key == upgrade
    assert row.activation_code is None


@pytest.mark.asyncio
async def test_never_calls_billing_service(_org_row, human_admin_token, license_code):
    await _reset_activation_fields(_org_row["id"])
    with patch("app.services.billing_client.sync_license", new_callable=AsyncMock) as mock_sync:
        resp = await _activate(human_admin_token, license_code("enterprise"))
    assert resp.status_code == 200
    mock_sync.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("make_code", [
    lambda make: "not-a-license-code",
    lambda make: make("enterprise", days=-1),
    lambda make: make("enterprise")[:-4] + "AAAA",
])
async def test_invalid_expired_or_tampered_code_returns_400_and_saves_nothing(
    _org_row, human_admin_token, license_code, make_code
):
    await _reset_activation_fields(_org_row["id"])
    resp = await _activate(human_admin_token, make_code(license_code))

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid activation code"
    row = await _license_row()
    assert row.license_key is None


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
