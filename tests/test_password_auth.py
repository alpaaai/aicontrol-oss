"""Tests for POST /auth/login (password-based auth replacing OTP)."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.models.database import async_session_factory


@pytest_asyncio.fixture(scope="session")
async def _auth_test_user():
    """Create a test user with known password for login tests, clean up after."""
    from app.routers.setup import _hash_password
    from app.models.user import User, UserRole
    import uuid

    user_id = uuid.uuid4()
    email = "logintest@example.com"
    pw_hash = _hash_password("correctpassword")

    async with async_session_factory() as db:
        await db.execute(
            text("""
                INSERT INTO users (id, email, name, role, is_active, password_hash, password_set, created_at)
                VALUES (:id, :email, 'Login Test', 'admin', true, :pw_hash, true, now())
                ON CONFLICT (email) DO UPDATE
                  SET password_hash = EXCLUDED.password_hash,
                      password_set = true,
                      is_active = true
            """),
            {"id": str(user_id), "email": email, "pw_hash": pw_hash},
        )
        await db.commit()

    yield {"email": email, "password": "correctpassword"}

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
        await db.commit()


@pytest_asyncio.fixture(scope="session")
async def _inactive_user():
    """Create an inactive test user."""
    from app.routers.setup import _hash_password
    import uuid

    user_id = uuid.uuid4()
    email = "inactive@example.com"
    pw_hash = _hash_password("correctpassword")

    async with async_session_factory() as db:
        await db.execute(
            text("""
                INSERT INTO users (id, email, name, role, is_active, password_hash, password_set, created_at)
                VALUES (:id, :email, 'Inactive', 'admin', false, :pw_hash, true, now())
                ON CONFLICT (email) DO UPDATE
                  SET is_active = false,
                      password_hash = EXCLUDED.password_hash
            """),
            {"id": str(user_id), "email": email, "pw_hash": pw_hash},
        )
        await db.commit()

    yield {"email": email, "password": "correctpassword"}

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
        await db.commit()


@pytest.mark.asyncio
async def test_login_success(_auth_test_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/login", json={
            "email": _auth_test_user["email"],
            "password": _auth_test_user["password"],
        })
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["user"]["email"] == _auth_test_user["email"]
    assert "first_login" in body


@pytest.mark.asyncio
async def test_login_wrong_password(_auth_test_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/login", json={
            "email": _auth_test_user["email"],
            "password": "wrongpassword",
        })
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_unknown_email():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/login", json={
            "email": "nobody@example.com",
            "password": "irrelevant",
        })
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_inactive_user(_inactive_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/login", json={
            "email": _inactive_user["email"],
            "password": _inactive_user["password"],
        })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_updates_last_login(_auth_test_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/auth/login", json={
            "email": _auth_test_user["email"],
            "password": _auth_test_user["password"],
        })
    async with async_session_factory() as db:
        result = await db.execute(
            text("SELECT last_login FROM users WHERE email = :e"),
            {"e": _auth_test_user["email"]},
        )
        last_login = result.scalar_one()
    assert last_login is not None
