"""Tests for GET /audit-events with filters and pagination."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
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


@pytest.mark.asyncio
async def test_community_audit_events_filtered_to_7_days(human_admin_token):
    """Community plan: events older than 7 days must not appear."""
    from app.core import license_gate
    from app.core.license import LicenseInfo
    community = LicenseInfo(plan="community", company=None, email=None, expires_at=None)

    with patch.object(license_gate, "get_license_info", return_value=community):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/audit-events",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    assert r.status_code == 200
    events = r.json()["events"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for event in events:
        event_time = datetime.fromisoformat(event["created_at"])
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        assert event_time >= cutoff, f"Event {event['id']} is older than 7 days"


@pytest.mark.asyncio
async def test_business_audit_events_not_filtered(human_admin_token):
    """Business plan: no 7-day filter — full history returned."""
    from app.core import license_gate
    from app.core.license import LicenseInfo
    business = LicenseInfo(plan="business", company="Acme", email="a@acme.com", expires_at=None)

    with patch.object(license_gate, "get_license_info", return_value=business):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get(
                "/audit-events",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    assert r.status_code == 200
