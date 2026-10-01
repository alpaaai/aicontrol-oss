"""GET /license/features tells the frontend which destinations exist."""
import pytest
from httpx import AsyncClient, ASGITransport

from app.core import license_gate
from app.core.license_gate import LicenseInfo
from app.main import app


@pytest.mark.asyncio
async def test_free_tier_reports_paid_features_off(human_admin_token, monkeypatch):
    async def _fake(db):
        return LicenseInfo(plan="community", company=None, email=None, expires_at=None)

    monkeypatch.setattr(license_gate, "get_license_info", _fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/license/features", headers={"Authorization": f"Bearer {human_admin_token}"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "free"
    assert body["features"]["nl_authoring"] is False
    assert body["features"]["simulation"] is False
    assert body["features"]["hitl"] is False
    assert body["features"]["compliance_reports"] is False


@pytest.mark.asyncio
async def test_enterprise_tier_reports_paid_features_on(human_admin_token, monkeypatch):
    async def _fake(db):
        return LicenseInfo(plan="enterprise", company=None, email=None, expires_at=None,
                            license_status="active")

    monkeypatch.setattr(license_gate, "get_license_info", _fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/license/features", headers={"Authorization": f"Bearer {human_admin_token}"}
        )
    body = resp.json()
    assert body["tier"] == "enterprise"
    assert all(body["features"].values())


@pytest.mark.asyncio
async def test_no_subscription_reports_null_license_status(human_admin_token, monkeypatch):
    async def _fake(db):
        return LicenseInfo(plan="community", company=None, email=None, expires_at=None)

    monkeypatch.setattr(license_gate, "get_license_info", _fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/license/features", headers={"Authorization": f"Bearer {human_admin_token}"}
        )
    body = resp.json()
    assert body["tier"] == "free"
    assert body["license_status"] is None


@pytest.mark.asyncio
async def test_active_business_reports_business_tier_and_active_status(human_admin_token, monkeypatch):
    async def _fake(db):
        return LicenseInfo(plan="business", company=None, email=None, expires_at=None,
                            license_status="active")

    monkeypatch.setattr(license_gate, "get_license_info", _fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/license/features", headers={"Authorization": f"Bearer {human_admin_token}"}
        )
    body = resp.json()
    assert body["tier"] == "business"
    assert body["license_status"] == "active"
    assert body["features"]["hitl"] is True
    assert body["features"]["nl_authoring"] is False


@pytest.mark.asyncio
async def test_past_due_business_keeps_tier_but_reports_past_due_status(human_admin_token, monkeypatch):
    """A past_due business org still sees its business-tier nav (tier
    unchanged) -- the frontend uses license_status to render a reactivate
    banner instead of hiding the nav entirely."""
    async def _fake(db):
        return LicenseInfo(plan="business", company=None, email=None, expires_at=None,
                            license_status="past_due")

    monkeypatch.setattr(license_gate, "get_license_info", _fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/license/features", headers={"Authorization": f"Bearer {human_admin_token}"}
        )
    body = resp.json()
    assert body["tier"] == "business"
    assert body["license_status"] == "past_due"
    assert body["features"]["hitl"] is True
