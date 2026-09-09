import uuid
import pytest

from app.models.mcp_server import MCPServer


@pytest.mark.asyncio
async def test_mcp_server_status_validates(db_session):
    server = MCPServer(id=uuid.uuid4(), name="test-mcp-server-1", base_url="https://mcp.example.com")
    db_session.add(server)
    await db_session.flush()
    assert server.status == "pending_review"

    with pytest.raises(ValueError):
        MCPServer(id=uuid.uuid4(), name="test-mcp-server-2", base_url="https://mcp.example.com", status="not_a_real_status")
