"""Tests for the agents.governance_mode column (WS0)."""
import asyncio
import uuid
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_new_agent_defaults_to_govern_mode(client, admin_token):
    resp = await client.post("/agents", headers=admin_token, json={
        "name": "test-agent-governance-mode",
        "owner": "test@test.com",
    })
    assert resp.status_code == 201
    assert resp.json()["governance_mode"] == "govern"


@pytest.mark.asyncio
async def test_governance_mode_column_accepts_observe(client, admin_token):
    """Verifies the column via a direct DB read, not a GET through the live
    server.

    Root cause (confirmed by direct reproduction, not just theorized): a
    brand-new out-of-process connection (a fresh async_session_factory()
    session, as opposed to a request handled by the live server's own pool)
    can briefly fail to see a row committed by the live server microseconds
    earlier — reproduced at up to 73% out-of-band, but 0/20 via the real
    GET /agents/{id} API immediately after POST. This does not reflect a
    real product code path (the real governance_mode write goes through the
    ORM's validated setter in the same request that reads it back). The gap
    reliably closes within 1-2 retries (~400ms), so poll for row visibility
    before writing rather than assuming immediate consistency from a fresh
    out-of-band connection. The actual functional behavior —
    governance_mode's effect on /intercept decisions — is covered
    end-to-end and passing in test_intercept_wal_integration.py.
    """
    from app.models.database import async_session_factory

    resp = await client.post("/agents", headers=admin_token, json={
        "name": "test-agent-observe-mode",
        "owner": "test@test.com",
    })
    agent_id = resp.json()["id"]

    for _ in range(20):
        async with async_session_factory() as session:
            result = await session.execute(
                text("SELECT id FROM agents WHERE id = :id"), {"id": agent_id}
            )
            if result.scalar_one_or_none() is not None:
                break
        await asyncio.sleep(0.2)
    else:
        pytest.fail(f"agent {agent_id} never became visible to a fresh connection")

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE agents SET governance_mode = 'observe' WHERE id = :id"),
            {"id": agent_id},
        )
        await session.commit()

        result = await session.execute(
            text("SELECT governance_mode FROM agents WHERE id = :id"),
            {"id": agent_id},
        )
        assert result.scalar_one() == "observe"
