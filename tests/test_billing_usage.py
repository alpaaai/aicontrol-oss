import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
from app.main import app
from app.core.license import LicenseInfo
from app.core import license_gate


def _community():
    return LicenseInfo(plan="community", company=None, email=None, expires_at=None)

def _business():
    return LicenseInfo(plan="business", company="Acme", email="a@acme.com", expires_at=None)

def _enterprise():
    return LicenseInfo(plan="enterprise", company="Aon", email="a@aon.com", expires_at=None)


@pytest.mark.asyncio
async def test_billing_usage_community_plan(human_admin_token):
    with patch.object(license_gate, "get_license_info", return_value=_community()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "community"
    assert data["retention_days"] == 7
    assert "this_month" in data
    assert "last_month" in data
    assert data["monthly_base_usd"] == 0.0
    assert data["rate_per_million"] == 0.0
    assert "features" in data
    assert isinstance(data["this_month"]["intercepts"], int)


@pytest.mark.asyncio
async def test_billing_usage_business_plan(human_admin_token):
    with patch.object(license_gate, "get_license_info", return_value=_business()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "business"
    assert data["retention_days"] is None   # unlimited
    assert data["monthly_base_usd"] == 49.0
    assert data["rate_per_million"] == 15.0
    assert "estimated_cost_usd" in data["this_month"]


@pytest.mark.asyncio
async def test_billing_usage_enterprise_plan(human_admin_token):
    with patch.object(license_gate, "get_license_info", return_value=_enterprise()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "enterprise"
    assert data["rate_per_million"] == 25.25
    assert data["monthly_base_usd"] == 149.0


@pytest.mark.asyncio
async def test_billing_usage_requires_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/billing/usage")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_billing_estimated_cost_calculation(human_admin_token):
    """500,000 intercepts on business plan = $15 * 0.5 = $7.50"""
    with patch.object(license_gate, "get_license_info", return_value=_business()):
        with patch("app.routers.billing.count_intercepts_in_period",
                   new_callable=AsyncMock, return_value=500_000):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                r = await client.get(
                    "/billing/usage",
                    headers={"Authorization": f"Bearer {human_admin_token}"},
                )
    data = r.json()
    assert data["this_month"]["intercepts"] == 500_000
    assert data["this_month"]["estimated_cost_usd"] == pytest.approx(7.50, rel=1e-3)
