import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_users_list_requires_admin(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/users", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)


@pytest.mark.asyncio
async def test_users_list_returns_expected_fields(human_admin_token, seed_admin_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/users", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) > 0
    u = users[0]
    assert "id" in u
    assert "email" in u
    assert "name" in u
    assert "role" in u
    assert "is_active" in u
    assert "last_login" in u
    assert "created_at" in u
