"""Regression test: pytest-fixture-issued api_tokens must not accumulate across runs."""
import pytest
import pytest_asyncio
from sqlalchemy import text

from app.models.database import async_session_factory
from tests.conftest import _delete_pytest_fixture_tokens

_LEAK_DESCRIPTIONS = ("pytest-admin-fixture", "pytest-agent-fixture")


@pytest.mark.asyncio
async def test_delete_pytest_fixture_tokens_removes_leaked_rows():
    async with async_session_factory() as db:
        for desc in _LEAK_DESCRIPTIONS:
            await db.execute(
                text("""
                    INSERT INTO api_tokens (id, token_hash, role, description, revoked)
                    VALUES (gen_random_uuid(), :hash, 'admin', :desc, false)
                """),
                {"hash": f"leaked-hash-{desc}", "desc": desc},
            )
        await db.commit()

    async with async_session_factory() as db:
        await _delete_pytest_fixture_tokens(db)
        await db.commit()

    async with async_session_factory() as db:
        result = await db.execute(
            text("SELECT count(*) FROM api_tokens WHERE description = ANY(:descs)"),
            {"descs": list(_LEAK_DESCRIPTIONS)},
        )
        assert result.scalar_one() == 0
