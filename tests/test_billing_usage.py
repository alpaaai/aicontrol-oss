import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
from app.main import app
from app.core.license_gate import LicenseInfo
from app.core import license_gate


def _community():
    return LicenseInfo(plan="community", company=None, email=None, expires_at=None)

def _business(license_status="active"):
    return LicenseInfo(plan="business", company="Acme", email="a@acme.com", expires_at=None,
                        license_status=license_status)

def _enterprise():
    return LicenseInfo(plan="enterprise", company="Acme", email="a@acme.com", expires_at=None)

def _trial():
    return LicenseInfo(plan="trial", company="Acme", email="a@acme.com", expires_at=None)


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
    assert data["annual_price_usd"] == 0.0
    assert "features" in data
    assert isinstance(data["this_month"]["intercepts"], int)
    assert "estimated_cost_usd" not in data["this_month"]
    assert "rate_per_million" not in data


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
    assert data["retention_days"] == 30
    assert data["annual_price_usd"] == 999.0
    assert "estimated_cost_usd" not in data["this_month"]


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
    assert data["retention_days"] == 90
    assert data["annual_price_usd"] == 1999.0


@pytest.mark.asyncio
async def test_billing_usage_enterprise_features_has_no_contradictory_retention_claims(human_admin_token):
    """GA review finding: _cascaded_features concatenates every tier's
    features list up through the caller's own tier, and each tier's list
    restated the retention window itself as a feature string -- community
    "7-day retention", business "30-day retention", enterprise "90-day
    retention" -- so an enterprise/trial account's features array held all
    three side by side, alongside the correct retention_days=90 elsewhere
    in the same response. retention_days is the single source of truth;
    no per-tier retention string belongs in features at all."""
    with patch.object(license_gate, "get_license_info", return_value=_enterprise()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    data = r.json()
    retention_mentions = [f for f in data["features"] if "retention" in f.lower()]
    assert retention_mentions == []


@pytest.mark.asyncio
async def test_billing_usage_trial_plan_returns_200_with_enterprise_features(human_admin_token):
    """plans/v4 task 13: PLAN_CONFIG[info.plan] must not KeyError for
    plan='trial'; the trial card reads the same features list object as
    enterprise, not a concatenation of business+enterprise."""
    from app.routers.billing import PLAN_CONFIG

    with patch.object(license_gate, "get_license_info", return_value=_trial()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "trial"
    assert data["features"] == PLAN_CONFIG["enterprise"]["features"]
    assert data["retention_days"] == 90
    assert data["annual_price_usd"] == 0.0


@pytest.mark.asyncio
async def test_billing_usage_community_features_are_community_only(human_admin_token):
    from app.routers.billing import PLAN_CONFIG

    with patch.object(license_gate, "get_license_info", return_value=_community()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    assert r.json()["features"] == PLAN_CONFIG["community"]["features"]


@pytest.mark.asyncio
async def test_billing_usage_business_features_include_community(human_admin_token):
    from app.routers.billing import PLAN_CONFIG

    with patch.object(license_gate, "get_license_info", return_value=_business()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    features = r.json()["features"]
    assert features == PLAN_CONFIG["community"]["features"] + PLAN_CONFIG["business"]["features"]
    assert not any("Everything in" in f for f in features)


@pytest.mark.asyncio
async def test_billing_usage_enterprise_features_include_community_and_business(human_admin_token):
    from app.routers.billing import PLAN_CONFIG

    with patch.object(license_gate, "get_license_info", return_value=_enterprise()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    features = r.json()["features"]
    assert features == (
        PLAN_CONFIG["community"]["features"]
        + PLAN_CONFIG["business"]["features"]
        + PLAN_CONFIG["enterprise"]["features"]
    )
    assert not any("Everything in" in f for f in features)




@pytest.mark.asyncio
async def test_billing_usage_requires_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/billing/usage")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_billing_usage_intercepts_count_is_informational_only(human_admin_token):
    """Task 14: usage stays operational visibility only -- no dollar
    estimate is derived from the intercept count anymore."""
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
    assert "estimated_cost_usd" not in data["this_month"]


@pytest.mark.asyncio
async def test_billing_usage_has_no_billing_service_fields(human_admin_token):
    """The billing-service sync is gone: /billing/usage reads the signed code
    only and never calls out."""
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
    assert "manage_subscription_url" not in data
    assert "license_synced_at" not in data


@pytest.mark.asyncio
async def test_billing_usage_includes_license_status_and_expires_at(human_admin_token):
    expires = datetime(2026, 12, 1, 9, 30, tzinfo=timezone.utc)
    info = LicenseInfo(plan="community", company="Acme", email="a@acme.com",
                       expires_at=expires, license_status="expired")
    with patch.object(license_gate, "get_license_info", return_value=info):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    data = r.json()
    assert data["license_status"] == "expired"
    assert data["expires_at"].startswith("2026-12-01")


@pytest.mark.asyncio
async def test_billing_usage_expires_at_null_without_a_code(human_admin_token):
    with patch.object(license_gate, "get_license_info", return_value=_community()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/billing/usage",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    data = r.json()
    assert data["license_status"] is None
    assert data["expires_at"] is None


def test_month_bounds_end_is_exclusive_start_of_next_month():
    """count_intercepts_in_period uses created_at < date_to. The end bound was
    the month's last day at 23:59:59, so every event in that final second was
    counted in neither month."""
    from datetime import datetime

    from app.routers.billing import _month_bounds

    assert _month_bounds(2026, 2) == (datetime(2026, 2, 1), datetime(2026, 3, 1))
    assert _month_bounds(2026, 12) == (datetime(2026, 12, 1), datetime(2027, 1, 1))


def test_cascaded_features_tolerates_an_unknown_plan():
    """billing_usage() looked up PLAN_CONFIG[plan] and TIER_ORDER.index(plan)
    directly, so any license_plan value outside the known four was a 500."""
    from app.routers.billing import PLAN_CONFIG, _cascaded_features

    assert _cascaded_features("something_new") == _cascaded_features("community")
    assert PLAN_CONFIG.get("something_new") is None


@pytest.mark.asyncio
async def test_billing_upgrade_endpoint_is_removed(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/billing/upgrade",
            json={"plan": "business"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert r.status_code in (404, 405)
