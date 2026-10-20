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


@pytest.mark.asyncio
async def test_root_user_cannot_be_deactivated_or_demoted(human_admin_token):
    """The root user is the account created by first-run setup. DELETE already
    refuses it; PATCH let an admin deactivate or demote it, which can leave an
    install with no way to sign in as an admin."""
    import uuid
    from sqlalchemy import text
    from app.models.database import async_session_factory

    root_id = uuid.uuid4()
    async with async_session_factory() as s:
        await s.execute(text("""
            INSERT INTO users (id, email, name, role, is_active, is_root, password_set, created_at)
            VALUES (:id, :email, 'Root Protect', 'admin', true, true, true, now())
        """), {"id": str(root_id), "email": f"test_root_{root_id.hex[:8]}@aicontrol.dev"})
        await s.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            headers = {"Authorization": f"Bearer {human_admin_token}"}
            deactivate = await c.patch(f"/users/{root_id}", json={"is_active": False}, headers=headers)
            demote = await c.patch(f"/users/{root_id}", json={"role": "analyst"}, headers=headers)
            noop = await c.patch(f"/users/{root_id}", json={"role": "admin", "is_active": True}, headers=headers)
        assert deactivate.status_code == 400
        assert demote.status_code == 400
        assert noop.status_code == 200
    finally:
        async with async_session_factory() as s:
            await s.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(root_id)})
            await s.commit()
