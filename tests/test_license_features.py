"""GET /license/features tells the frontend which destinations exist."""
import pytest
from httpx import AsyncClient, ASGITransport

from app.core import license_gate
from app.core.license import LicenseInfo
from app.main import app


@pytest.mark.asyncio
async def test_free_tier_reports_paid_features_off(human_admin_token, monkeypatch):
    monkeypatch.setattr(
        license_gate,
        "get_license_info",
        lambda: LicenseInfo(plan="community", company=None, email=None, expires_at=None),
    )
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
    monkeypatch.setattr(
        license_gate,
        "get_license_info",
        lambda: LicenseInfo(plan="enterprise", company=None, email=None, expires_at=None),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/license/features", headers={"Authorization": f"Bearer {human_admin_token}"}
        )
    body = resp.json()
    assert body["tier"] == "enterprise"
    assert all(body["features"].values())
