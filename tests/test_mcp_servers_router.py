import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_register_mcp_server_requires_admin(agent_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/mcp-servers",
            json={"name": "test-mcp-server-reg-1", "base_url": "https://mcp.example.com/mcp"},
            headers=agent_token,
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_mcp_server_as_admin(admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/mcp-servers",
            json={"name": "test-mcp-server-reg-2", "base_url": "https://mcp.example.com/mcp"},
            headers=admin_token,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending_review"
    assert body["approved_tools"] == []
    assert "base_url" in body
    # Decision 9: no credential field in the response, ever.
    assert "auth_token" not in body
    assert "auth_type" not in body


@pytest.mark.asyncio
async def test_list_mcp_servers(admin_token, db_session):
    from app.models.mcp_server import MCPServer
    import uuid as uuid_mod

    server = MCPServer(id=uuid_mod.uuid4(), name="test-mcp-server-list-1", base_url="https://mcp.example.com")
    db_session.add(server)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/mcp-servers", headers=admin_token)
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "test-mcp-server-list-1" in names


@pytest.mark.asyncio
async def test_get_mcp_server_404_when_missing(admin_token):
    import uuid as uuid_mod

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/mcp-servers/{uuid_mod.uuid4()}", headers=admin_token)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_mcp_server_activates_it(admin_token, db_session):
    from app.models.mcp_server import MCPServer
    import uuid as uuid_mod

    server = MCPServer(id=uuid_mod.uuid4(), name="test-mcp-server-patch-1", base_url="https://mcp.example.com")
    db_session.add(server)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/mcp-servers/{server.id}",
            json={"status": "active", "approved_tools": ["safe_tool"]},
            headers=admin_token,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    assert resp.json()["approved_tools"] == ["safe_tool"]


@pytest.mark.asyncio
async def test_patch_mcp_server_rejects_invalid_status(admin_token, db_session):
    from app.models.mcp_server import MCPServer
    import uuid as uuid_mod

    server = MCPServer(id=uuid_mod.uuid4(), name="test-mcp-server-patch-2", base_url="https://mcp.example.com")
    db_session.add(server)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/mcp-servers/{server.id}", json={"status": "not_a_real_status"}, headers=admin_token,
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_mcp_server(admin_token, db_session):
    from app.models.mcp_server import MCPServer
    import uuid as uuid_mod

    server = MCPServer(id=uuid_mod.uuid4(), name="test-mcp-server-delete-1", base_url="https://mcp.example.com")
    db_session.add(server)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/mcp-servers/{server.id}", headers=admin_token)
    assert resp.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp2 = await client.get(f"/mcp-servers/{server.id}", headers=admin_token)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_mcp_servers_router_is_mounted():
    from app.main import app as main_app
    paths = {route.path for route in main_app.routes}
    assert "/mcp-servers" in paths
    assert "/mcp-servers/{server_id}" in paths
