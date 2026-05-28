"""Tests for POST /auth/request-code and POST /auth/verify-code."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_request_code_unknown_email_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/auth/request-code", json={"email": "nobody@example.com"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_request_code_known_email_returns_200(seed_admin_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/auth/request-code", json={"email": "admin@aicontrol.dev"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Code sent"
    assert "dev_code" in data


@pytest.mark.asyncio
async def test_verify_code_wrong_code_returns_401(seed_admin_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/auth/request-code", json={"email": "admin@aicontrol.dev"})
        resp = await client.post(
            "/auth/verify-code", json={"email": "admin@aicontrol.dev", "code": "000000"}
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_code_correct_returns_token(seed_admin_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post("/auth/request-code", json={"email": "admin@aicontrol.dev"})
        code = r1.json()["dev_code"]
        r2 = await client.post(
            "/auth/verify-code", json={"email": "admin@aicontrol.dev", "code": code}
        )
    assert r2.status_code == 200
    assert "token" in r2.json()
