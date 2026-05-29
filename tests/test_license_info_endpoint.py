"""Tests for GET /license-info — public endpoint for frontend plan detection."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from fastapi import HTTPException

from app.main import app
from app.core.license import LicenseInfo


@pytest.fixture
def community_info():
    return LicenseInfo(plan="community", company=None, email=None, expires_at=None)


@pytest.fixture
def enterprise_info():
    return LicenseInfo(
        plan="enterprise", company="Aon", email="admin@aon.com", expires_at=None
    )


@pytest.mark.asyncio
async def test_license_info_community(community_info):
    with patch("app.routers.license.get_license_info", return_value=community_info):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/license-info")
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "community"
    assert data["is_enterprise"] is False
    assert data["is_business"] is False
    assert "email" not in data
    assert "jti" not in data


@pytest.mark.asyncio
async def test_license_info_enterprise(enterprise_info):
    with patch("app.routers.license.get_license_info", return_value=enterprise_info):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/license-info")
    assert r.status_code == 200
    data = r.json()
    assert data["plan"] == "enterprise"
    assert data["is_enterprise"] is True
    assert data["is_business"] is True
    assert data["company"] == "Aon"


@pytest.mark.asyncio
async def test_license_info_no_auth_required(community_info):
    """Endpoint must be publicly accessible — no token needed."""
    with patch("app.routers.license.get_license_info", return_value=community_info):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/license-info")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_license_info_invalid_key_returns_402():
    with patch(
        "app.routers.license.get_license_info",
        side_effect=HTTPException(status_code=402, detail="expired"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/license-info")
    assert r.status_code == 402
