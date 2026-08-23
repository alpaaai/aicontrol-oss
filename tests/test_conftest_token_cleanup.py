"""Regression test: pytest-fixture-issued api_tokens must not accumulate across runs.

This file previously called _delete_pytest_fixture_tokens() with its real default
descriptions against the shared dev database, which deleted the *live* tokens that
the session-scoped _seed_and_token_setup fixture had already issued. Every later
test using the admin_token or agent_token fixture then got 401 from the live API.
The helper is exercised against throwaway probe descriptions instead, so the
deletion mechanism is still covered without disarming the running session.
"""
import pytest
from sqlalchemy import text

from app.models.database import async_session_factory
from tests.conftest import (
    _PYTEST_FIXTURE_TOKEN_DESCRIPTIONS,
    _PROBE_TOKEN_DESCRIPTIONS,
    _delete_pytest_fixture_tokens,
)


async def _insert_probe_tokens():
    async with async_session_factory() as db:
        for desc in _PROBE_TOKEN_DESCRIPTIONS:
            await db.execute(
                text("""
                    INSERT INTO api_tokens (id, token_hash, role, description, revoked)
                    VALUES (gen_random_uuid(), :hash, 'admin', :desc, false)
                """),
                {"hash": f"leaked-hash-{desc}", "desc": desc},
            )
        await db.commit()


async def _count(descs):
    async with async_session_factory() as db:
        return (await db.execute(
            text("SELECT count(*) FROM api_tokens WHERE description = ANY(:descs)"),
            {"descs": list(descs)},
        )).scalar_one()


@pytest.mark.asyncio
async def test_delete_pytest_fixture_tokens_removes_leaked_rows():
    await _insert_probe_tokens()
    assert await _count(_PROBE_TOKEN_DESCRIPTIONS) == len(_PROBE_TOKEN_DESCRIPTIONS)

    async with async_session_factory() as db:
        await _delete_pytest_fixture_tokens(db, descriptions=_PROBE_TOKEN_DESCRIPTIONS)
        await db.commit()

    assert await _count(_PROBE_TOKEN_DESCRIPTIONS) == 0


@pytest.mark.asyncio
async def test_delete_pytest_fixture_tokens_leaves_other_descriptions_alone(
    _seed_and_token_setup,
):
    """The helper must delete only the descriptions it is given. Guards the exact
    regression this file used to cause: wiping the live session fixture tokens."""
    await _insert_probe_tokens()
    live_before = await _count(_PYTEST_FIXTURE_TOKEN_DESCRIPTIONS)
    assert live_before > 0, "session fixture tokens should be live at this point"

    async with async_session_factory() as db:
        await _delete_pytest_fixture_tokens(db, descriptions=_PROBE_TOKEN_DESCRIPTIONS)
        await db.commit()

    assert await _count(_PROBE_TOKEN_DESCRIPTIONS) == 0
    assert await _count(_PYTEST_FIXTURE_TOKEN_DESCRIPTIONS) == live_before


@pytest.mark.asyncio
async def test_cleanup_fixture_targets_the_real_fixture_descriptions():
    """The probe run above only proves the mechanism. This pins the constant the
    autouse cleanup fixture actually passes, which is what stops cross-run leaks."""
    assert _PYTEST_FIXTURE_TOKEN_DESCRIPTIONS == (
        "pytest-admin-fixture",
        "pytest-agent-fixture",
    )
    assert not set(_PROBE_TOKEN_DESCRIPTIONS) & set(_PYTEST_FIXTURE_TOKEN_DESCRIPTIONS)
