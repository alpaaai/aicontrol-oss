"""Tests for the mcp_servers table (WS1)."""
import uuid
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_mcp_servers_table_accepts_a_row_and_defaults_to_pending_scan():
    from app.models.database import async_session_factory

    server_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO mcp_servers (id, name, base_url, auth_type)
            VALUES (:id, 'test-mcp-server', 'https://mcp.example.com/mcp', 'none')
        """), {"id": str(server_id)})
        await session.commit()

        result = await session.execute(
            text("SELECT status, approved_tools FROM mcp_servers WHERE id = :id"),
            {"id": str(server_id)},
        )
        row = result.one()
        assert row.status == "pending_scan"
        assert row.approved_tools == []

        await session.execute(text("DELETE FROM mcp_servers WHERE id = :id"), {"id": str(server_id)})
        await session.commit()
