"""Tests for user activity log — write_activity_log and GET /dashboard/activity-log."""
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@contextmanager
def _admin_auth_override():
    from app.core.auth import _get_verified_token
    app.dependency_overrides[_get_verified_token] = lambda: {"role": "admin", "email": None}
    try:
        yield
    finally:
        app.dependency_overrides.pop(_get_verified_token, None)


def _opa_patch():
    return patch("app.routers.policies.invalidate_policy_set_cache", new=AsyncMock(return_value=None))


@pytest.mark.asyncio
async def test_activity_log_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/dashboard/activity-log")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_policy_update_creates_activity_log(human_admin_token, seed_policy):
    policy_id = seed_policy
    with _admin_auth_override(), _opa_patch():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put(
                f"/policies/{policy_id}",
                json={"description": "Updated via activity log test"},
            )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/activity-log",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    assert any(l["action"] == "policy.update" for l in logs)


@pytest.mark.asyncio
async def test_agent_crud_creates_activity_log(human_admin_token):
    name = f"test-agent-actlog-{uuid.uuid4().hex[:6]}"
    with _admin_auth_override():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post(
                "/agents", json={"name": name, "owner": "test@example.com"},
            )
            assert create_resp.status_code == 201
            agent_id = create_resp.json()["id"]

            update_resp = await client.put(f"/agents/{agent_id}", json={"owner": "new-owner@example.com"})
            assert update_resp.status_code == 200

            tools_resp = await client.patch(
                f"/agents/{agent_id}/approved-tools", json={"approved_tools": ["safe_tool"]},
            )
            assert tools_resp.status_code == 200

            delete_resp = await client.delete(f"/agents/{agent_id}")
            assert delete_resp.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/activity-log",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    actions = {l["action"] for l in logs if l["resource_id"] == agent_id}
    assert actions == {"agent.create", "agent.update", "agent.approved_tools_update", "agent.delete"}


@pytest.mark.asyncio
async def test_mcp_server_crud_creates_activity_log(human_admin_token):
    name = f"test-mcp-server-actlog-{uuid.uuid4().hex[:6]}"
    with _admin_auth_override():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post(
                "/mcp-servers", json={"name": name, "base_url": "https://mcp.example.com/mcp"},
            )
            assert create_resp.status_code == 201
            server_id = create_resp.json()["id"]

            update_resp = await client.patch(f"/mcp-servers/{server_id}", json={"status": "active"})
            assert update_resp.status_code == 200

            delete_resp = await client.delete(f"/mcp-servers/{server_id}")
            assert delete_resp.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/activity-log",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    actions = {l["action"] for l in logs if l["resource_id"] == server_id}
    assert actions == {"mcp_server.create", "mcp_server.update", "mcp_server.delete"}
