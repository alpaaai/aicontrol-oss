"""Tests for GET /sessions and GET /sessions/{id}/events."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.core.license_gate import require_enterprise_license
from app.main import app


@pytest.fixture(autouse=True)
def _bypass_enterprise_license_gate():
    """This file's tests aren't about licensing -- bypass
    require_enterprise_license the same way test_audit_export.py bypasses
    it, rather than relying on ambient org_settings state."""
    app.dependency_overrides[require_enterprise_license] = lambda: None
    yield
    app.dependency_overrides.pop(require_enterprise_license, None)


@pytest.mark.asyncio
async def test_sessions_list_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/sessions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sessions_list_returns_list(human_admin_token, seed_sessions):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/sessions",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


@pytest.mark.asyncio
async def test_session_events_returns_events_for_session(human_admin_token, seed_sessions):
    session_id = seed_sessions[0]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/sessions/{session_id}/events",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert all(e["session_id"] == str(session_id) for e in data["events"])


@pytest.mark.asyncio
async def test_session_events_unknown_session_returns_404(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/sessions/00000000-0000-0000-0000-000000000000/events",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 404
