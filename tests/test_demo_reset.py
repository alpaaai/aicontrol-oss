import uuid
import pytest
from sqlalchemy import text

from app.models.database import async_session_factory
from scripts.demo_reset import reset, DEMO_MCP_SERVER_NAMES
from scripts.seed import AGENTS


@pytest.mark.asyncio
async def test_reset_clears_admission_scans_and_named_mcp_servers():
    scan_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text(
            "INSERT INTO admission_scans (id, target_type, target_ref, scanner_name, status, findings, severity_summary) "
            "VALUES (:id, 'skill', '/tmp/x', 'skill_scanner', 'completed', '[]', '{}')"
        ), {"id": scan_id})
        await session.execute(text(
            "INSERT INTO mcp_servers (id, name, base_url) VALUES (gen_random_uuid(), :name, 'http://x')"
        ), {"name": DEMO_MCP_SERVER_NAMES[0]})
        await session.commit()

    await reset()

    async with async_session_factory() as session:
        remaining_scans = (await session.execute(text("SELECT COUNT(*) FROM admission_scans"))).scalar_one()
        remaining_server = (await session.execute(
            text("SELECT COUNT(*) FROM mcp_servers WHERE name = :name"), {"name": DEMO_MCP_SERVER_NAMES[0]}
        )).scalar_one()
        assert remaining_scans == 0
        assert remaining_server == 0


@pytest.mark.asyncio
async def test_reset_clears_sessions_for_every_seeded_agent():
    other_agent_id = AGENTS[1]["id"]  # not the hardcoded AGENT_ID
    session_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text(
            "INSERT INTO sessions (id, agent_id, status) VALUES (:id, :agent_id, 'active') ON CONFLICT DO NOTHING"
        ), {"id": session_id, "agent_id": other_agent_id})
        await session.commit()

    await reset()

    async with async_session_factory() as session:
        remaining = (await session.execute(
            text("SELECT COUNT(*) FROM sessions WHERE id = :id"), {"id": session_id}
        )).scalar_one()
        assert remaining == 0
