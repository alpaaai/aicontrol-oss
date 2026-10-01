"""Tests for GET /audit-events with filters and pagination."""
import csv
import io
import json
import uuid

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.models.database import async_session_factory


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
async def test_audit_events_filter_by_decision_accepts_error(human_admin_token):
    """decision=error was rejected with 422 (pattern only allowed
    allow|deny|review) until the JSON-RPC error audit fix added a fourth
    decision value the gateway can actually write."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/audit-events?decision=error",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200


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
    from app.core.license_gate import LicenseInfo
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
    from app.core.license_gate import LicenseInfo
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


@pytest_asyncio.fixture(scope="session")
async def seed_audit_event_with_parameters():
    """GA review finding: list_audit_events used to return tool_parameters
    as str(dict)[:120] -- a Python repr (single-quoted), not JSON, silently
    truncated. Seeds one event with a real JSONB payload to catch that
    regression."""
    event_id = uuid.uuid4()
    session_id = uuid.uuid4()
    params = {"repoName": "modelcontextprotocol/modelcontextprotocol", "nested": {"a": 1}}
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO sessions (id, agent_id, started_at)
            VALUES (:sid, (SELECT id FROM agents LIMIT 1), NOW())
        """), {"sid": str(session_id)})
        await db.execute(text("""
            INSERT INTO audit_events (id, session_id, sequence_number, tool_name, tool_parameters, decision, created_at)
            VALUES (:id, :sid, 1, 'test_filter_tool_params', CAST(:params AS jsonb), 'allow', NOW())
        """), {"id": str(event_id), "sid": str(session_id), "params": json.dumps(params)})
        await db.commit()

    yield event_id, params

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(event_id)})
        await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(session_id)})
        await db.commit()


@pytest.mark.asyncio
async def test_audit_events_returns_tool_parameters_as_real_json(human_admin_token, seed_audit_event_with_parameters):
    event_id, params = seed_audit_event_with_parameters
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/audit-events?tool_name=test_filter_tool_params",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    events = [e for e in resp.json()["events"] if e["id"] == str(event_id)]
    assert len(events) == 1
    assert events[0]["tool_parameters"] == params


@pytest.mark.asyncio
async def test_audit_events_export_includes_tool_parameters(human_admin_token, seed_audit_event_with_parameters):
    event_id, params = seed_audit_event_with_parameters
    from app.core import license_gate
    from app.core.license_gate import LicenseInfo
    enterprise = LicenseInfo(plan="enterprise", company="Acme", email="a@acme.com", expires_at=None, license_status="active")

    with patch.object(license_gate, "get_license_info", return_value=enterprise):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/audit-events/export?tool_name=test_filter_tool_params",
                headers={"Authorization": f"Bearer {human_admin_token}"},
            )
    assert resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    matching = [r for r in rows if r["id"] == str(event_id)]
    assert len(matching) == 1
    assert json.loads(matching[0]["tool_parameters"]) == params
