import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_dashboard_summary_has_new_fields(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/dashboard/summary", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "active_warnings" in data
    assert "overdue_reviews" in data
    assert "top_denied_tool" in data
    assert "high_risk_sessions" in data
    assert isinstance(data["active_warnings"], int)
    assert isinstance(data["overdue_reviews"], int)
    assert isinstance(data["high_risk_sessions"], int)
    # top_denied_tool may be None if no deny events today
    assert data["top_denied_tool"] is None or isinstance(data["top_denied_tool"], dict)
