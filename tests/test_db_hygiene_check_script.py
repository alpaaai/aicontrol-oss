"""Tests for the scripts/db_hygiene_check.py CLI's pure reporting logic
and end-to-end report/--fix exit-code contract against a real leaked row."""
import uuid

import pytest
from sqlalchemy import text

from app.models.database import async_session_factory
from scripts import db_hygiene, db_hygiene_check


def test_format_report_lists_only_nonzero_labels():
    report = db_hygiene_check.format_report({"agents": 2, "policies": 0, "api_tokens": 1})
    assert "agents: 2" in report
    assert "api_tokens: 1" in report
    assert "policies" not in report


def test_format_report_on_a_clean_db():
    assert db_hygiene_check.format_report({"agents": 0, "policies": 0}) == "No leaked test/demo rows found."


@pytest.mark.asyncio
async def test_main_reports_without_deleting_when_fix_is_false():
    agent_id = str(uuid.uuid4())
    async with async_session_factory() as session:
        await session.execute(text(
            "INSERT INTO agents (id, name, owner, status, approved_tools) "
            "VALUES (:id, :name, 'nobody@test.dev', 'active', '[]'::jsonb)"
        ), {"id": agent_id, "name": f"test-agent-cli-check-{agent_id[:8]}"})
        await session.commit()

    exit_code = await db_hygiene_check.main(fix=False)
    assert exit_code == 1

    async with async_session_factory() as session:
        result = await session.execute(text("SELECT 1 FROM agents WHERE id = :id"), {"id": agent_id})
        assert result.first() is not None, "report-only mode must not delete anything"
        await db_hygiene.clean_all(session)


@pytest.mark.asyncio
async def test_main_deletes_when_fix_is_true():
    agent_id = str(uuid.uuid4())
    async with async_session_factory() as session:
        await session.execute(text(
            "INSERT INTO agents (id, name, owner, status, approved_tools) "
            "VALUES (:id, :name, 'nobody@test.dev', 'active', '[]'::jsonb)"
        ), {"id": agent_id, "name": f"test-agent-cli-fix-{agent_id[:8]}"})
        await session.commit()

    exit_code = await db_hygiene_check.main(fix=True)
    assert exit_code == 0

    async with async_session_factory() as session:
        result = await session.execute(text("SELECT 1 FROM agents WHERE id = :id"), {"id": agent_id})
        assert result.first() is None


@pytest.mark.asyncio
async def test_main_returns_zero_on_an_already_clean_db():
    async with async_session_factory() as session:
        await db_hygiene.clean_all(session)
    assert await db_hygiene_check.main(fix=False) == 0
