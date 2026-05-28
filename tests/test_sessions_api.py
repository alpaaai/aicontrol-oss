"""Tests for GET /sessions and GET /sessions/{id}/events."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


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
