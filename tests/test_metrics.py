import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_expected_shape(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/dashboard/metrics", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "policy_hit_rate" in data
    assert "deny_trend" in data
    assert "top_agents_by_deny_rate" in data
    assert "avg_review_seconds" in data
    assert isinstance(data["policy_hit_rate"], float)
    assert isinstance(data["deny_trend"], list)
    assert isinstance(data["top_agents_by_deny_rate"], list)
