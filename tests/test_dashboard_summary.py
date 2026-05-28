"""Tests for GET /dashboard/summary and GET /dashboard/activity-log."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

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
