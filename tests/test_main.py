"""Tests for FastAPI app and /health endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_health_returns_200():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_json_status_ok():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_includes_service_name():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    data = response.json()
    assert "service" in data
    assert data["service"] == "aicontrol"


@pytest.mark.asyncio
async def test_health_reports_enterprise_only_when_license_invalid():
    """An invalid/expired license key must not 402 or crash /health (2.5 fix) --
    has_enterprise_license() raising HTTPException is caught and treated as
    'not enterprise', same as no key set."""
    from app.main import app
    with patch("app.main.has_enterprise_license", side_effect=HTTPException(status_code=402, detail="invalid")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["drift_detector_status"] == "enterprise_only"


@pytest.mark.asyncio
async def test_health_reports_enterprise_only_for_business_plan():
    """A Business-tier (non-enterprise) license key must not report a live
    drift_detector_status -- the detector never starts for that plan (2.5 fix:
    startup used to gate on bare key presence, not the decoded plan)."""
    from app.main import app
    with patch("app.main.has_enterprise_license", return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["drift_detector_status"] == "enterprise_only"
