"""GET /agents/{id}/policies — every policy scoped to this agent, as sentences."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(loop_scope="session")
async def make_agent():
    from app.models.database import async_session_factory

    async def _make(**columns) -> uuid.UUID:
        agent_id = uuid.uuid4()
        columns.setdefault("name", f"test-agent-govpol-{agent_id.hex[:8]}")
        cols = {"id": agent_id, "owner": "tests", "status": "active", **columns}
        names = ", ".join(cols)
        binds = ", ".join(f":{k}" for k in cols)
        async with async_session_factory() as session:
            await session.execute(
                text(f"INSERT INTO agents ({names}) VALUES ({binds})"), cols
            )
            await session.commit()
        return agent_id

    return _make


@pytest_asyncio.fixture(loop_scope="session")
async def make_policy():
    from app.models.database import async_session_factory

    created_ids = []

    async def _make(**columns):
        policy_id = uuid.uuid4()
        columns.setdefault("condition", "{}")
        cols = {
            "id": policy_id,
            "active": True,
            "library": False,
            "priority": 100,
            **columns,
        }
        names = ", ".join(cols)
        binds = []
        for k in cols:
            if k == "condition":
                binds.append(f"CAST(:{k} AS jsonb)")
            else:
                binds.append(f":{k}")
        async with async_session_factory() as session:
            await session.execute(
                text(f"INSERT INTO policies ({names}) VALUES ({', '.join(binds)})"), cols
            )
            await session.commit()
        created_ids.append(policy_id)
        return policy_id

    yield _make

    from app.models.database import async_session_factory
    async with async_session_factory() as session:
        for pid in created_ids:
            await session.execute(text("DELETE FROM policies WHERE id = :id"), {"id": pid})
        await session.commit()


@pytest.mark.asyncio
async def test_returns_policies_scoped_to_named_agent(
    client, admin_token, make_agent, make_policy
):
    agent_id = await make_agent(name="test-agent-govpol-target")
    await make_policy(
        name="test-govpol-review-payment",
        principal_type="agent",
        principal_id="test-agent-govpol-target",
        action_tool="release_payment",
        resource_system="guidewire",
        effect="review",
    )
    resp = await client.get(f"/agents/{agent_id}/policies", headers=admin_token)
    assert resp.status_code == 200, resp.text
    names = {p["principalId"] for p in resp.json()}
    assert "test-agent-govpol-target" in names


@pytest.mark.asyncio
async def test_excludes_policies_scoped_to_other_agents(
    client, admin_token, make_agent, make_policy
):
    agent_id = await make_agent(name="test-agent-govpol-lonely")
    await make_policy(
        name="test-govpol-other-agent",
        principal_type="agent",
        principal_id="someone-else-entirely",
        action_tool="release_payment",
        resource_system="guidewire",
        effect="deny",
    )
    resp = await client.get(f"/agents/{agent_id}/policies", headers=admin_token)
    assert resp.status_code == 200
    ids = {p["principalId"] for p in resp.json()}
    assert "someone-else-entirely" not in ids


@pytest.mark.asyncio
async def test_includes_unscoped_policies_that_apply_to_every_agent(
    client, admin_token, make_agent, make_policy
):
    agent_id = await make_agent(name="test-agent-govpol-universal")
    policy_id = await make_policy(
        name="test-govpol-unscoped",
        principal_type=None,
        principal_id=None,
        action_tool=None,
        resource_system=None,
        effect="deny",
    )
    resp = await client.get(f"/agents/{agent_id}/policies", headers=admin_token)
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert str(policy_id) in ids


@pytest.mark.asyncio
async def test_unknown_agent_returns_404(client, admin_token):
    resp = await client.get(f"/agents/{uuid.uuid4()}/policies", headers=admin_token)
    assert resp.status_code == 404
