"""Tests for enterprise/app/routers/audit_export_config.py (business-tier gated).

Uses ASGITransport (in-process), not the client fixture (live server at
localhost:8001) -- same reasoning as tests/enterprise/test_discovery_api.py.
"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture(autouse=True)
def _bypass_business_license():
    from app.main import app
    from app.core.license_gate import require_business_license
    app.dependency_overrides[require_business_license] = lambda: None
    yield
    app.dependency_overrides.pop(require_business_license, None)


@pytest.mark.asyncio
async def test_create_list_and_delete_audit_export_config(admin_token):
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/audit-export-configs",
            json={"export_type": "webhook", "target_url": "http://collector.internal/webhook"},
            headers=admin_token,
        )
        assert create_resp.status_code == 201
        config_id = create_resp.json()["id"]
        assert create_resp.json()["enabled"] is True

        list_resp = await client.get("/audit-export-configs", headers=admin_token)
        assert any(c["id"] == config_id for c in list_resp.json())

        delete_resp = await client.delete(f"/audit-export-configs/{config_id}", headers=admin_token)
        assert delete_resp.status_code == 204

        list_resp_after = await client.get("/audit-export-configs", headers=admin_token)
        assert not any(c["id"] == config_id for c in list_resp_after.json())


@pytest.mark.asyncio
async def test_create_rejects_invalid_export_type(admin_token):
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/audit-export-configs",
            json={"export_type": "carrier_pigeon", "target_url": "http://collector.internal/webhook"},
            headers=admin_token,
        )
        assert resp.status_code == 422
