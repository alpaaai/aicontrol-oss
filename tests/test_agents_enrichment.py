import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_agent_list_includes_enriched_fields(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/agents", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) > 0
    agent = agents[0]
    assert "system_prompt_hash" in agent
    assert "approved_at" in agent
    assert "created_at" in agent
    assert "last_active" in agent
    assert "deny_rate" in agent


@pytest.mark.asyncio
async def test_agent_deny_rate_is_float_or_none(human_admin_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/agents", headers={"Authorization": f"Bearer {human_admin_token}"})
    agents = resp.json()
    for a in agents:
        dr = a["deny_rate"]
        assert dr is None or isinstance(dr, float)
