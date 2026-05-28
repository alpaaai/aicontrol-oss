"""Tests for GET /audit-events with filters and pagination."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_audit_events_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/audit-events")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_audit_events_returns_list(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/audit-events",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "total" in data
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_audit_events_filter_by_decision(human_admin_token, seed_audit_events):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/audit-events?decision=deny",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert all(e["decision"] == "deny" for e in data["events"])


@pytest.mark.asyncio
async def test_audit_events_pagination(human_admin_token, seed_audit_events):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/audit-events?limit=5&offset=0",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    assert len(resp.json()["events"]) <= 5
