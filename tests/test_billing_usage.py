import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
from app.main import app
from app.core.license_gate import LicenseInfo
from app.core import license_gate


def _community():
    return LicenseInfo(plan="community", company=None, email=None, expires_at=None)

def _business(license_status=None):
    return LicenseInfo(plan="business", company="Acme", email="a@acme.com", expires_at=None,
                        license_status=license_status)

def _enterprise():
    return LicenseInfo(plan="enterprise", company="Aon", email="a@aon.com", expires_at=None)

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


def test_compliance_export_feature_string_matches_implemented_frameworks():
    """5.1: the billing feature list must match the frameworks the compliance
    report generator actually supports, not an invented set."""
    from app.routers.billing import PLAN_CONFIG
    from enterprise.compliance.prompt_builder import ALLOWED_FRAMEWORKS

    compliance_features = [
        f for f in PLAN_CONFIG["enterprise"]["features"] if "Compliance report export" in f
    ]
    assert len(compliance_features) == 1
    feature_string = compliance_features[0]
    for framework_label in ["SOC 2", "EU AI Act", "NIST AI RMF", "ISO 42001"]:
        assert framework_label in feature_string
    for wrong_label in ["PCI", "HIPAA", "GLBA"]:
        assert wrong_label not in feature_string
    assert ALLOWED_FRAMEWORKS == {"eu_ai_act", "nist_ai_rmf", "soc2", "iso_42001"}


@pytest.mark.asyncio
async def test_billing_usage_requires_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/billing/usage")
    assert r.status_code == 401


async def _set_activation_code(code):
    """Replace org_settings with a single known row carrying the given
    activation_code; caller restores via _restore_org_settings."""
    from sqlalchemy import text
    from app.models.database import async_session_factory

    async with async_session_factory() as db:
        saved = (await db.execute(text("SELECT id, org_name, timezone FROM org_settings"))).fetchall()
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(
            text("""
                INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at, activation_code)
                VALUES (gen_random_uuid(), 'Acme', 'UTC', now(), now(), :code)
            """),
            {"code": code},
        )
        await db.commit()
    return saved


async def _restore_org_settings(existing):
    from sqlalchemy import text
    from app.models.database import async_session_factory

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


@pytest.mark.asyncio
async def test_billing_usage_with_activation_code_populates_billing_urls(human_admin_token):
    saved = await _set_activation_code("test-activation-code")
    try:
        with patch.object(license_gate, "get_license_info", return_value=_business()), \
             patch(
                 "app.routers.billing.fetch_billing_urls",
                 new_callable=AsyncMock,
                 return_value={"manage_subscription_url": "https://billing.stripe.com/session/abc", "upgrade_url": None},
             ) as mock_fetch:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                r = await client.get(
                    "/billing/usage",
                    headers={"Authorization": f"Bearer {human_admin_token}"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["manage_subscription_url"] == "https://billing.stripe.com/session/abc"
        assert data["upgrade_url"] is None
        mock_fetch.assert_called_once_with("test-activation-code", "business")
    finally:
        await _restore_org_settings(saved)


@pytest.mark.asyncio
async def test_billing_usage_without_activation_code_leaves_urls_none_and_skips_call(human_admin_token):
    saved = await _set_activation_code(None)
    try:
        with patch.object(license_gate, "get_license_info", return_value=_community()), \
             patch(
                 "app.routers.billing.fetch_billing_urls", new_callable=AsyncMock
             ) as mock_fetch:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                r = await client.get(
                    "/billing/usage",
                    headers={"Authorization": f"Bearer {human_admin_token}"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["manage_subscription_url"] is None
        assert data["upgrade_url"] is None
        mock_fetch.assert_not_called()
    finally:
        await _restore_org_settings(saved)


@pytest.mark.asyncio
async def test_billing_usage_falls_back_to_none_when_billing_client_fails(human_admin_token):
    from app.services.billing_client import BillingClientError

    saved = await _set_activation_code("test-activation-code")
    try:
        with patch.object(license_gate, "get_license_info", return_value=_business()), \
             patch(
                 "app.routers.billing.fetch_billing_urls",
                 new_callable=AsyncMock,
                 side_effect=BillingClientError("billing-service unreachable"),
             ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                r = await client.get(
                    "/billing/usage",
                    headers={"Authorization": f"Bearer {human_admin_token}"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["manage_subscription_url"] is None
        assert data["upgrade_url"] is None
    finally:
        await _restore_org_settings(saved)


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


async def _set_activation_code_and_synced_at(code, synced_at):
    """Like _set_activation_code but also sets license_synced_at, for
    plans/v4 task 24's BillingPage.tsx fields."""
    from sqlalchemy import text
    from app.models.database import async_session_factory

    async with async_session_factory() as db:
        saved = (await db.execute(text("SELECT id, org_name, timezone FROM org_settings"))).fetchall()
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(
            text("""
                INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at,
                                           activation_code, license_synced_at)
                VALUES (gen_random_uuid(), 'Acme', 'UTC', now(), now(), :code, :synced_at)
            """),
            {"code": code, "synced_at": synced_at},
        )
        await db.commit()
    return saved


@pytest.mark.asyncio
async def test_billing_usage_includes_license_status_and_synced_at(human_admin_token):
    """plans/v4 task 24 note: BillingPage.tsx reads license_status and
    license_synced_at off /billing/usage rather than a second endpoint call."""
    synced_at = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    saved = await _set_activation_code_and_synced_at("test-activation-code", synced_at)
    try:
        with patch.object(license_gate, "get_license_info", return_value=_business(license_status="past_due")), \
             patch("app.routers.billing.fetch_billing_urls", new_callable=AsyncMock,
                   return_value={"manage_subscription_url": "https://billing.stripe.com/session/abc", "upgrade_url": None}):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                r = await client.get(
                    "/billing/usage",
                    headers={"Authorization": f"Bearer {human_admin_token}"},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["license_status"] == "past_due"
        assert data["license_synced_at"] is not None
        assert data["license_synced_at"].startswith("2026-09-15")
    finally:
        await _restore_org_settings(saved)


@pytest.mark.asyncio
async def test_billing_usage_license_synced_at_null_when_never_synced(human_admin_token):
    saved = await _set_activation_code(None)
    try:
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
        assert data["license_status"] is None
        assert data["license_synced_at"] is None
    finally:
        await _restore_org_settings(saved)
