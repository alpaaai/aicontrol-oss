import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.license_gate import require_enterprise_license


@pytest.mark.asyncio
async def test_audit_export_requires_enterprise(human_admin_token):
    """Community plan gets 402 from enterprise gate."""
    from unittest.mock import patch
    with patch("app.core.license_gate.get_license_info") as mock_lic:
        mock_lic.return_value = type("L", (), {"plan": "community", "is_enterprise": False})()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                "/audit-events/export",
                headers={"Authorization": f"Bearer {human_admin_token}"}
            )
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_audit_export_returns_csv(human_admin_token):
    """Enterprise plan receives a valid CSV file."""
    app.dependency_overrides[require_enterprise_license] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                "/audit-events/export",
                headers={"Authorization": f"Bearer {human_admin_token}"}
            )
    finally:
        app.dependency_overrides.pop(require_enterprise_license, None)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "id,created_at" in resp.text
