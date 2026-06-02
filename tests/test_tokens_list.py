import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_token_list_requires_admin(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/tokens", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert isinstance(tokens, list)
    for t in tokens:
        assert "token_hash" not in t
        assert "id" in t
        assert "role" in t
        assert "revoked" in t
        assert "created_at" in t


@pytest.mark.asyncio
async def test_token_list_never_returns_token_hash(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/tokens", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    for t in resp.json():
        assert "token_hash" not in t
