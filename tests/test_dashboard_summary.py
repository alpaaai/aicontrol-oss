"""Tests for GET /dashboard/summary and GET /dashboard/activity-log."""
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.models.database import async_session_factory

REQUIRED_SUMMARY_KEYS = [
    "intercepts_today", "intercepts_7d", "intercepts_30d",
    "allow_count_today", "deny_count_today", "review_count_today",
    "deny_rate_today", "active_sessions",
    "pending_reviews", "active_agents", "active_policies",
    "top_tools", "decisions_by_hour",
]


@pytest.mark.asyncio
async def test_dashboard_summary_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/dashboard/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_summary_shape(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/summary",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    for key in REQUIRED_SUMMARY_KEYS:
        assert key in data, f"Missing key: {key}"


@pytest_asyncio.fixture(scope="session")
async def seed_single_old_audit_event():
    """Seed exactly one audit event 10 days in the past, no others in the 30-day window."""
    session_id = uuid.uuid4()
    event_id = uuid.uuid4()
    created_at = datetime.utcnow() - timedelta(days=10)
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO sessions (id, agent_id, started_at)
            VALUES (:sid, (SELECT id FROM agents LIMIT 1), :started_at)
        """), {"sid": str(session_id), "started_at": created_at})
        await db.execute(text("""
            INSERT INTO audit_events (id, session_id, sequence_number, tool_name, decision, created_at)
            VALUES (:id, :sid, 1, 'test_old_tool', 'allow', :created_at)
        """), {"id": str(event_id), "sid": str(session_id), "created_at": created_at})
        await db.commit()

    yield

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": str(event_id)})
        await db.execute(text("DELETE FROM sessions WHERE id = :id"), {"id": str(session_id)})
        await db.commit()


@pytest.mark.asyncio
async def test_decisions_by_hour_zero_fills_sparse_days(human_admin_token, seed_single_old_audit_event):
    """The 30-day chart must have a bucket for every day in the window, not just days with events."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/dashboard/summary",
            headers={"Authorization": f"Bearer {human_admin_token}"},
        )
    assert resp.status_code == 200
    decisions_by_hour = resp.json()["decisions_by_hour"]
    distinct_days = {row["hour"][:10] for row in decisions_by_hour}
    assert len(distinct_days) >= 30, (
        f"Expected 30 zero-filled days in the window, got {len(distinct_days)}"
    )
