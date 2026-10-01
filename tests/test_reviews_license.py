"""Tests for business-license gating on /reviews (GET list + PATCH resolve)."""
import uuid
from unittest.mock import patch

import pytest
import app.core.license_gate as _lg
from app.core.license_gate import LicenseInfo
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_get_reviews_requires_business_license(human_admin_token):
    """GET /reviews returns 402 without a business/enterprise license (community plan)."""
    from app.main import app
    _community = LicenseInfo(plan="community", company=None, email=None, expires_at=None)

    with patch.object(_lg, "get_license_info", return_value=_community):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/reviews", headers={"Authorization": f"Bearer {human_admin_token}"}
            )

    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "business_required"


@pytest.mark.asyncio
async def test_patch_review_requires_business_license(human_admin_token):
    """PATCH /reviews/{id} returns 402 without a business/enterprise license (community plan)."""
    from app.main import app
    _community = LicenseInfo(plan="community", company=None, email=None, expires_at=None)

    with patch.object(_lg, "get_license_info", return_value=_community):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/reviews/{uuid.uuid4()}",
                json={"action": "approve"},
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )

    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "business_required"


@pytest.mark.asyncio
async def test_patch_review_allows_business_license(human_admin_token):
    """PATCH /reviews/{id} must succeed for a business-plan license, not just enterprise --
    this is the tier split fixed in audit task 5.4: Slack-based review actions were already
    available at Business tier, the API path is now aligned to match."""
    from app.main import app
    from app.models.database import async_session_factory
    from sqlalchemy import text

    _business = LicenseInfo(
        plan="business", company=None, email=None, expires_at=None, license_status="active"
    )
    review_id = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text(
            "INSERT INTO hitl_reviews (id, status, created_at) VALUES (:id, 'pending', NOW())"
        ), {"id": str(review_id)})
        await db.commit()

    try:
        with patch.object(_lg, "get_license_info", return_value=_business):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.patch(
                    f"/reviews/{review_id}",
                    json={"action": "approve"},
                    headers={"Authorization": f"Bearer {human_admin_token}"},
                )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"
    finally:
        async with async_session_factory() as db:
            await db.execute(text("DELETE FROM hitl_reviews WHERE id = :id"), {"id": str(review_id)})
            await db.commit()
