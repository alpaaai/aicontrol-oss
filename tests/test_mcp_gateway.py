"""Tests for the MCP Native Proxy gateway (WS1, business tier).

Uses ASGITransport against enterprise.mcp_gateway.main.gateway_app directly —
this is a separate FastAPI app object from app.main.app, not mounted on it.
"""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from sqlalchemy import text


@pytest_asyncio.fixture(loop_scope="session")
async def active_mcp_server():
    from app.models.database import async_session_factory

    server_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO mcp_servers (id, name, base_url, auth_type, status, approved_tools)
            VALUES (:id, 'test-gateway-server', 'https://mcp.example.com/mcp', 'none', 'active', '["safe_tool"]'::jsonb)
        """), {"id": str(server_id)})
        await session.commit()
    yield server_id
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM mcp_servers WHERE id = :id"), {"id": str(server_id)})
        await session.commit()


@pytest.mark.asyncio
async def test_tools_list_filters_to_approved_tools(active_mcp_server):
    from enterprise.mcp_gateway.main import gateway_app

    upstream_tools = {"tools": [{"name": "safe_tool"}, {"name": "unapproved_tool"}]}
    with patch(
        "enterprise.mcp_gateway.main.forward_to_upstream",
        new=AsyncMock(return_value=upstream_tools),
    ):
        async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as client:
            resp = await client.post(f"/mcp/{active_mcp_server}/tools/list", json={})

    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()["tools"]]
    assert names == ["safe_tool"]


@pytest.mark.asyncio
async def test_call_tool_denies_unapproved_tool_without_forwarding(active_mcp_server):
    from enterprise.mcp_gateway.main import gateway_app

    with patch("enterprise.mcp_gateway.main.forward_to_upstream", new=AsyncMock()) as mock_forward:
        async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as client:
            resp = await client.post(f"/mcp/{active_mcp_server}/call_tool", json={
                "name": "unapproved_tool", "arguments": {},
            })

    assert resp.status_code == 200
    body = resp.json()
    assert body["isError"] is True
    assert "policy" in body["content"][0]["text"].lower()
    mock_forward.assert_not_called()


@pytest.mark.asyncio
async def test_call_tool_forwards_approved_tool(active_mcp_server):
    from enterprise.mcp_gateway.main import gateway_app

    with patch(
        "enterprise.mcp_gateway.main.forward_to_upstream",
        new=AsyncMock(return_value={"content": [{"type": "text", "text": "ok"}], "isError": False}),
    ) as mock_forward:
        async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as client:
            resp = await client.post(f"/mcp/{active_mcp_server}/call_tool", json={
                "name": "safe_tool", "arguments": {"x": 1},
            })

    assert resp.status_code == 200
    assert resp.json()["isError"] is False
    mock_forward.assert_called_once()


@pytest.mark.asyncio
async def test_call_tool_unknown_server_returns_404():
    from enterprise.mcp_gateway.main import gateway_app

    async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as client:
        resp = await client.post(f"/mcp/{uuid.uuid4()}/call_tool", json={"name": "x", "arguments": {}})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_call_tool_denied_by_active_opa_policy(active_mcp_server, admin_token, client):
    """A tool_denylist policy on 'safe_tool' (approved at the server level)
    must still deny at the OPA layer — approved_tools is necessary, not
    sufficient."""
    from enterprise.mcp_gateway.main import gateway_app

    await client.post("/policies", headers=admin_token, json={
        "name": "test_gateway_denylist_safe_tool",
        "description": "Deny safe_tool globally, to prove gateway checks OPA too",
        "rule_type": "tool_denylist",
        "condition": {"blocked_tools": ["safe_tool"]},
        "action": "deny", "severity": "critical", "active": True,
    })

    with patch("enterprise.mcp_gateway.main.forward_to_upstream", new=AsyncMock()) as mock_forward:
        async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as gw_client:
            resp = await gw_client.post(f"/mcp/{active_mcp_server}/call_tool", json={
                "name": "safe_tool", "arguments": {},
            })

    assert resp.json()["isError"] is True
    mock_forward.assert_not_called()
