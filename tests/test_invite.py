"""Tests for magic link invite system."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.models.database import async_session_factory


def _make_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def _seed_invited_user(email: str) -> tuple[dict, str, str]:
    """Return (insert params, plaintext_token, token_hash) for an invited user."""
    uid = str(uuid.uuid4())
    token, token_hash = _make_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    return (
        {"id": uid, "email": email, "hash": token_hash, "exp": expires_at},
        token,
        token_hash,
    )


@pytest_asyncio.fixture(scope="session")
async def _invited_user():
    """User with a valid invite token — used for validate and set-password tests."""
    email = "invited@example.com"
    params, token, _ = _seed_invited_user(email)
    async with async_session_factory() as db:
        await db.execute(
            text("""
                INSERT INTO users (id, email, name, role, is_active, password_set,
                                   invite_token_hash, invite_expires_at, created_at)
                VALUES (:id, :email, 'Invite Test', 'analyst', true, false,
                        :hash, :exp, now())
                ON CONFLICT (email) DO UPDATE
                  SET invite_token_hash = EXCLUDED.invite_token_hash,
                      invite_expires_at = EXCLUDED.invite_expires_at,
                      password_set = false
            """),
            params,
        )
        await db.commit()
        result = await db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email})
        user_id = str(result.scalar_one())
    yield {"email": email, "token": token, "user_id": user_id}
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
        await db.commit()


@pytest_asyncio.fixture(scope="session")
async def _regen_user():
    """Separate user for regenerate-invite tests (keeps _invited_user token intact)."""
    email = "regen@example.com"
    params, token, _ = _seed_invited_user(email)
    async with async_session_factory() as db:
        await db.execute(
            text("""
                INSERT INTO users (id, email, name, role, is_active, password_set,
                                   invite_token_hash, invite_expires_at, created_at)
                VALUES (:id, :email, 'Regen Test', 'analyst', true, false,
                        :hash, :exp, now())
                ON CONFLICT (email) DO UPDATE
                  SET invite_token_hash = EXCLUDED.invite_token_hash,
                      invite_expires_at = EXCLUDED.invite_expires_at,
                      password_set = false
            """),
            params,
        )
        await db.commit()
        result = await db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email})
        user_id = str(result.scalar_one())
    yield {"email": email, "token": token, "user_id": user_id}
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
        await db.commit()


@pytest_asyncio.fixture(scope="session")
async def _password_set_user():
    """User who has already completed their invite (password_set=true)."""
    email = "alreadyset@example.com"
    uid = str(uuid.uuid4())
    async with async_session_factory() as db:
        await db.execute(
            text("""
                INSERT INTO users (id, email, name, role, is_active, password_set, created_at)
                VALUES (:id, :email, 'Already Set', 'analyst', true, true, now())
                ON CONFLICT (email) DO UPDATE SET password_set = true
            """),
            {"id": uid, "email": email},
        )
        await db.commit()
        result = await db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": email})
        user_id = str(result.scalar_one())
    yield {"email": email, "user_id": user_id}
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
        await db.commit()


@pytest_asyncio.fixture(scope="session")
async def _expired_token_user():
    """User with an expired invite token."""
    email = "expired@example.com"
    uid = str(uuid.uuid4())
    token, token_hash = _make_token()
    expired_at = datetime.now(timezone.utc) - timedelta(hours=1)
    async with async_session_factory() as db:
        await db.execute(
            text("""
                INSERT INTO users (id, email, name, role, is_active, password_set,
                                   invite_token_hash, invite_expires_at, created_at)
                VALUES (:id, :email, 'Expired', 'analyst', true, false,
                        :hash, :exp, now())
                ON CONFLICT (email) DO UPDATE
                  SET invite_token_hash = EXCLUDED.invite_token_hash,
                      invite_expires_at = EXCLUDED.invite_expires_at
            """),
            {"id": uid, "email": email, "hash": token_hash, "exp": expired_at},
        )
        await db.commit()
    yield {"email": email, "token": token}
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
        await db.commit()


# ── POST /auth/magic-link/validate ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_magic_link_valid(_invited_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/magic-link/validate", json={"token": _invited_user["token"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["email"] == _invited_user["email"]
    assert "full_name" in body


@pytest.mark.asyncio
async def test_validate_magic_link_expired(_expired_token_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/auth/magic-link/validate", json={"token": _expired_token_user["token"]}
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_validate_magic_link_invalid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/magic-link/validate", json={"token": "notarealtoken"})
    assert resp.status_code == 401


# ── POST /auth/set-password ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_password_success_returns_jwt(_invited_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/auth/set-password",
            json={"token": _invited_user["token"], "password": "newpassword123"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["user"]["email"] == _invited_user["email"]


@pytest.mark.asyncio
async def test_set_password_invalid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/auth/set-password",
            json={"token": "notarealtoken", "password": "validpassword"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_set_password_too_short():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/auth/set-password",
            json={"token": "notarealtoken", "password": "short"},
        )
    assert resp.status_code == 422


# ── POST /users ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user_returns_magic_link(human_admin_token):
    email = "newuser_ml_test@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/users",
            json={"full_name": "New User", "email": email, "role": "analyst"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "magic_link" in body
    assert "token=" in body["magic_link"]
    assert "user" in body
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
        await db.commit()


@pytest.mark.asyncio
async def test_create_user_409_duplicate_email(_invited_user, human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/users",
            json={"full_name": "Dupe", "email": _invited_user["email"], "role": "analyst"},
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 409


# ── POST /users/{id}/regenerate-invite ────────────────────────────────────────

@pytest.mark.asyncio
async def test_regenerate_invite_creates_new_token(_regen_user, human_admin_token):
    user_id = _regen_user["user_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/users/{user_id}/regenerate-invite",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "magic_link" in body
    new_token = body["magic_link"].split("token=")[1]
    assert new_token != _regen_user["token"]


@pytest.mark.asyncio
async def test_regenerate_invite_400_if_password_already_set(_password_set_user, human_admin_token):
    user_id = _password_set_user["user_id"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/users/{user_id}/regenerate-invite",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 400
