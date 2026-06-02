import pytest
import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.models.database import async_session_factory


@pytest_asyncio.fixture(scope="session")
async def seed_policy_with_agents():
    policy_id = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO policies (id, name, rule_type, condition, action,
                applies_to_agents, created_by, active)
            VALUES (:id, 'test_enrich_pol', 'tool_call', '{"tool":"any"}'::jsonb,
                    'allow', '["a1","a2","a3"]'::jsonb, 'alice@example.com', true)
        """), {"id": str(policy_id)})
        await db.commit()
    yield policy_id
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM policies WHERE id = :id"), {"id": str(policy_id)})
        await db.commit()


@pytest.mark.asyncio
async def test_policy_list_includes_applies_to_agents_count(human_admin_token, seed_policy_with_agents):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/policies", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    policies = resp.json()
    enriched = next(p for p in policies if p["id"] == str(seed_policy_with_agents))
    assert enriched["applies_to_agents"] == 3
    assert enriched["created_by"] == "alice@example.com"


@pytest.mark.asyncio
async def test_policy_list_applies_to_agents_defaults_to_zero(human_admin_token, seed_policy):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/policies", headers={"Authorization": f"Bearer {human_admin_token}"})
    assert resp.status_code == 200
    policies = resp.json()
    enriched = next(p for p in policies if p["id"] == str(seed_policy))
    assert enriched["applies_to_agents"] == 0
    assert enriched["created_by"] is None
