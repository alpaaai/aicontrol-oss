"""Tests for enterprise/app/routers/policy_authoring.py (enterprise-tier
gated -- matches warnings.py/compliance/router.py's convention for other
Enforce-tier capabilities, not the business-tier CRUD routers).

Uses ASGITransport (in-process), not the client fixture (live server on
localhost:8001) -- same reasoning as tests/enterprise/test_discovery_api.py:
app.dependency_overrides only affects the process it runs in.
"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture(autouse=True)
def _bypass_enterprise_license():
    from app.main import app
    from app.core.license_gate import require_enterprise_license
    app.dependency_overrides[require_enterprise_license] = lambda: None
    yield
    app.dependency_overrides.pop(require_enterprise_license, None)


@pytest.mark.asyncio
async def test_draft_endpoint_returns_pending_draft_not_active_policy(admin_token):
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/policies/nl-draft",
            json={"description": "Block any agent from calling delete_customer_record"},
            headers=admin_token,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] in ("drafted", "requires_manual_authoring")


@pytest.mark.asyncio
async def test_draft_endpoint_requires_enterprise_license(admin_token):
    """A community-plan request must be rejected -- self-critique finding:
    this router previously had no license gate at all, unlike every
    sibling enterprise router. This local dev environment's own .env holds
    a real enterprise license key, so simulate a community-plan denial
    explicitly (matching require_enterprise_license's real 402 shape)
    rather than relying on the ambient environment having no license."""
    from fastapi import HTTPException
    from app.main import app
    from app.core.license_gate import require_enterprise_license

    def _deny_enterprise():
        raise HTTPException(status_code=402, detail={"error": "enterprise_required"})

    app.dependency_overrides[require_enterprise_license] = _deny_enterprise

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/policies/nl-draft",
            json={"description": "Block any agent from calling delete_customer_record"},
            headers=admin_token,
        )
    assert resp.status_code == 402
