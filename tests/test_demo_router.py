"""Tests for /demo endpoints: status, seed, reset."""
import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_demo_status_returns_seeded_bool(client, admin_token):
    resp = await client.get("/demo/status", headers=admin_token)
    assert resp.status_code == 200
    data = resp.json()
    assert "seeded" in data
    assert isinstance(data["seeded"], bool)


@pytest.mark.asyncio
async def test_demo_status_has_demo_token_field(client, admin_token):
    resp = await client.get("/demo/status", headers=admin_token)
    assert resp.status_code == 200
    data = resp.json()
    assert "demo_token" in data


@pytest.mark.asyncio
async def test_demo_status_requires_auth(client):
    resp = await client.get("/demo/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_demo_seed_returns_ok(client, admin_token):
    resp = await client.post("/demo/seed", headers=admin_token)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "demo_token" in data
    assert isinstance(data["demo_token"], str)
    assert len(data["demo_token"]) > 0


@pytest.mark.asyncio
async def test_demo_seed_is_idempotent(client, admin_token):
    resp1 = await client.post("/demo/seed", headers=admin_token)
    resp2 = await client.post("/demo/seed", headers=admin_token)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["ok"] is True
    assert resp2.json()["ok"] is True


@pytest.mark.asyncio
async def test_demo_seed_sets_seeded_status(client, admin_token):
    await client.post("/demo/seed", headers=admin_token)
    resp = await client.get("/demo/status", headers=admin_token)
    assert resp.json()["seeded"] is True


@pytest.mark.asyncio
async def test_demo_seed_requires_admin(client, agent_token):
    resp = await client.post("/demo/seed", headers=agent_token)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_demo_reset_returns_ok(client, admin_token):
    await client.post("/demo/seed", headers=admin_token)
    resp = await client.post("/demo/reset", headers=admin_token)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_demo_reset_requires_admin(client, agent_token):
    resp = await client.post("/demo/reset", headers=agent_token)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_demo_reset_clears_sessions(client, admin_token, agent_token):
    """After reset, no sessions exist for demo agents."""
    from app.models.database import async_session_factory
    from sqlalchemy import text

    await client.post("/demo/seed", headers=admin_token)

    # Create a session for a demo agent
    demo_agent_id = "00000000-0000-0000-0000-000000000010"
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO sessions (id, agent_id, status)
            VALUES (gen_random_uuid(), :agent_id, 'active')
            ON CONFLICT DO NOTHING
        """), {"agent_id": demo_agent_id})
        await session.commit()

    resp = await client.post("/demo/reset", headers=admin_token)
    assert resp.status_code == 200

    async with async_session_factory() as session:
        result = await session.execute(text(
            "SELECT COUNT(*) FROM sessions WHERE agent_id = :agent_id"
        ), {"agent_id": demo_agent_id})
        count = result.scalar()

    assert count == 0
