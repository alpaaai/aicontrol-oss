"""Tests for enterprise-license gating on /sessions (list + session events)."""
from unittest.mock import patch

import pytest
import app.core.license_gate as _lg
from app.core.license import LicenseInfo
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_list_sessions_requires_enterprise_license(human_admin_token):
    """GET /sessions returns 402 without an enterprise license (community plan)."""
    from app.main import app
    _community = LicenseInfo(plan="community", company=None, email=None, expires_at=None)

    with patch.object(_lg, "get_license_info", return_value=_community):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/sessions", headers={"Authorization": f"Bearer {human_admin_token}"}
            )

    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "enterprise_required"


@pytest.mark.asyncio
async def test_session_events_requires_enterprise_license(human_admin_token):
    """GET /sessions/{id}/events returns 402 without an enterprise license."""
    import uuid
    from app.main import app
    _community = LicenseInfo(plan="community", company=None, email=None, expires_at=None)

    with patch.object(_lg, "get_license_info", return_value=_community):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/sessions/{uuid.uuid4()}/events",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )

    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "enterprise_required"
