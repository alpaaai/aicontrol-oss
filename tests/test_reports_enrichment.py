import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.license_gate import require_enterprise_license


@pytest.mark.asyncio
async def test_reports_list_includes_generated_by_email(human_admin_token):
    app.dependency_overrides[require_enterprise_license] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                "/enterprise/compliance/reports",
                headers={"Authorization": f"Bearer {human_admin_token}"}
            )
    finally:
        app.dependency_overrides.pop(require_enterprise_license, None)
    assert resp.status_code == 200
    reports = resp.json()
    assert isinstance(reports, list)
    for r in reports:
        assert "generated_by_email" in r
