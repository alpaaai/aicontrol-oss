"""Tests for FastAPI app and /health endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


@pytest.mark.asyncio
async def test_health_returns_200():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_json_status_ok():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_includes_service_name():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    data = response.json()
    assert "service" in data
    assert data["service"] == "aicontrol"


@pytest.mark.asyncio
async def test_health_reports_enterprise_only_when_license_is_expired(license_code):
    """An expired code must not 402 or crash /health -- it reads as community,
    so the drift detector is reported enterprise_only."""
    from sqlalchemy import text
    from app.main import app
    from app.models.database import async_session_factory
    from tests.conftest import restore_org_settings, snapshot_org_settings

    async with async_session_factory() as db:
        existing = await snapshot_org_settings(db)
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(
            text("""
                INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at, license_key)
                VALUES (gen_random_uuid(), 'Acme', 'UTC', now(), now(), :k)
            """),
            {"k": license_code("enterprise", days=-1)},
        )
        await db.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    finally:
        async with async_session_factory() as db:
            await restore_org_settings(db, existing)
            await db.commit()
    assert response.status_code == 200
    assert response.json()["drift_detector_status"] == "enterprise_only"


@pytest.mark.asyncio
async def test_health_reports_enterprise_only_for_business_plan():
    """A Business-tier (non-enterprise) license key must not report a live
    drift_detector_status -- the detector never starts for that plan (2.5 fix:
    startup used to gate on bare key presence, not the decoded plan)."""
    from app.main import app
    with patch("app.main.has_enterprise_license", return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["drift_detector_status"] == "enterprise_only"
