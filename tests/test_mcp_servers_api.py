"""Tests for enterprise/app/routers/mcp_servers.py (WS1, business-tier gated).

Uses ASGITransport (in-process) rather than the client fixture (live server
on localhost:8001) — unittest.mock.patch only affects the process it runs
in, and mocking McpScannerAdapter.scan_with_auth needs to actually take
effect for these tests to run without a real scanner binary/network call.
"""
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
import app.core.license_gate as _lg
from app.core.license import LicenseInfo


@contextmanager
def _with_business_license():
    _business = LicenseInfo(plan="business", company="Test", email="t@t.com", expires_at=None)
    with patch.object(_lg, "get_license_info", return_value=_business):
        yield


@contextmanager
def _mock_admin():
    from app.main import app
    from app.core.auth import require_admin
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


@contextmanager
def _mock_non_admin():
    """Simulate the real require_admin dependency's own rejection of a
    non-admin caller (its actual behavior is `if role != "admin": raise 403`
    — app/core/auth.py:86-93), without needing a real signed token."""
    from fastapi import HTTPException
    from app.main import app
    from app.core.auth import require_admin

    def _reject():
        raise HTTPException(status_code=403, detail="Admin role required")

    app.dependency_overrides[require_admin] = _reject
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_create_mcp_server_runs_scan_and_activates_when_clean():
    from app.main import app

    with _with_business_license(), _mock_admin(), patch(
        "enterprise.app.routers.mcp_servers.McpScannerAdapter.scan_with_auth",
        new=AsyncMock(return_value=[]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/mcp-servers", json={
                "name": "test-mcp-server-crud",
                "base_url": "https://mcp.example.com/mcp",
                "auth_type": "none",
            })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "active"
    assert data["approved_tools"] == []

    from app.models.database import async_session_factory
    from sqlalchemy import text
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM mcp_servers WHERE id = :id"), {"id": data["id"]})
        await session.commit()


@pytest.mark.asyncio
async def test_create_mcp_server_blocks_on_high_severity_finding():
    from app.main import app
    from app.services.scanners.port import Finding

    with _with_business_license(), _mock_admin(), patch(
        "enterprise.app.routers.mcp_servers.McpScannerAdapter.scan_with_auth",
        new=AsyncMock(return_value=[
            Finding(severity="high", rule_id="CODE EXECUTION", message="Detected code execution", location="execute_command"),
        ]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/mcp-servers", json={
                "name": "test-mcp-server-malicious",
                "base_url": "https://malicious.example.com/mcp",
                "auth_type": "none",
            })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "blocked"

    from app.models.database import async_session_factory
    from sqlalchemy import text
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM mcp_servers WHERE id = :id"), {"id": data["id"]})
        await session.commit()


@pytest.mark.asyncio
async def test_list_mcp_servers_requires_admin():
    from app.main import app

    with _with_business_license(), _mock_non_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/mcp-servers")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_mcp_server():
    from app.main import app

    with _with_business_license(), _mock_admin(), patch(
        "enterprise.app.routers.mcp_servers.McpScannerAdapter.scan_with_auth",
        new=AsyncMock(return_value=[]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post("/mcp-servers", json={
                "name": "test-mcp-server-delete", "base_url": "https://mcp2.example.com/mcp", "auth_type": "none",
            })
            server_id = create_resp.json()["id"]
            delete_resp = await client.delete(f"/mcp-servers/{server_id}")
            assert delete_resp.status_code == 204
            get_resp = await client.get("/mcp-servers")
    assert server_id not in [s["id"] for s in get_resp.json()]
