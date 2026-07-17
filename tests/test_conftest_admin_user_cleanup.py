"""Regression test: seed_admin_user must not leave a permanent user row behind."""
import pytest
from sqlalchemy import text

from app.models.database import async_session_factory
from tests.conftest import _ensure_admin_user, _remove_admin_user_if_created

_EMAIL = "admin@aicontrol.dev"


@pytest.mark.asyncio
async def test_ensure_admin_user_cleanup_removes_row_it_created():
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": _EMAIL})
        await db.commit()

    async with async_session_factory() as db:
        created = await _ensure_admin_user(db)
        await db.commit()
    assert created is True

    async with async_session_factory() as db:
        await _remove_admin_user_if_created(db, created)
        await db.commit()

    async with async_session_factory() as db:
        result = await db.execute(text("SELECT 1 FROM users WHERE email = :email"), {"email": _EMAIL})
        assert result.fetchone() is None


@pytest.mark.asyncio
async def test_ensure_admin_user_cleanup_preserves_preexisting_row():
    async with async_session_factory() as db:
        await db.execute(
            text("""
                INSERT INTO users (id, email, role, is_active, created_at)
                VALUES (gen_random_uuid(), :email, 'admin', true, now())
                ON CONFLICT (email) DO NOTHING
            """),
            {"email": _EMAIL},
        )
        await db.commit()

    try:
        async with async_session_factory() as db:
            created = await _ensure_admin_user(db)
            await db.commit()
        assert created is False

        async with async_session_factory() as db:
            await _remove_admin_user_if_created(db, created)
            await db.commit()

        async with async_session_factory() as db:
            result = await db.execute(text("SELECT 1 FROM users WHERE email = :email"), {"email": _EMAIL})
            assert result.fetchone() is not None
    finally:
        async with async_session_factory() as db:
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": _EMAIL})
            await db.commit()
