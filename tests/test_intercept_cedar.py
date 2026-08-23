"""/intercept evaluates via Cedar, and only against policies that scope to the call."""
import uuid

import pytest
from sqlalchemy import select

from app.models.schemas import Policy
from app.routers.intercept import get_scoped_policies


@pytest.mark.asyncio
async def test_scoped_query_excludes_policies_for_other_agents(db_session):
    mine = Policy(
        id=uuid.uuid4(), name="test_scoped_mine",
        condition={}, active=True,
        principal_type="agent", principal_id="agent-a",
        action_tool="http_post", resource_system=None, effect="deny",
        cedar_text="//x",
    )
    theirs = Policy(
        id=uuid.uuid4(), name="test_scoped_theirs",
        condition={}, active=True,
        principal_type="agent", principal_id="agent-b",
        action_tool="http_post", resource_system=None, effect="deny",
        cedar_text="//y",
    )
    db_session.add_all([mine, theirs])
    await db_session.flush()

    scoped = await get_scoped_policies(
        db_session, agent_name="agent-a", agent_groups=[],
        tool_name="http_post", system="unknown",
    )
    names = {p["name"] for p in scoped}
    assert "test_scoped_mine" in names
    assert "test_scoped_theirs" not in names


@pytest.mark.asyncio
async def test_scoped_query_includes_group_policies(db_session):
    group_policy = Policy(
        id=uuid.uuid4(), name="test_scoped_group",
        condition={}, active=True,
        principal_type="group", principal_id="finance",
        action_tool=None, resource_system=None, effect="deny", cedar_text="//z",
    )
    db_session.add(group_policy)
    await db_session.flush()

    scoped = await get_scoped_policies(
        db_session, agent_name="agent-a", agent_groups=["finance"],
        tool_name="anything", system="unknown",
    )
    assert "test_scoped_group" in {p["name"] for p in scoped}


@pytest.mark.asyncio
async def test_scoped_query_excludes_wrong_system(db_session):
    p = Policy(
        id=uuid.uuid4(), name="test_scoped_system",
        condition={}, active=True,
        principal_type="agent", principal_id="agent-a",
        action_tool=None, resource_system="netsuite", effect="deny", cedar_text="//w",
    )
    db_session.add(p)
    await db_session.flush()

    scoped = await get_scoped_policies(
        db_session, agent_name="agent-a", agent_groups=[],
        tool_name="http_post", system="salesforce",
    )
    assert "test_scoped_system" not in {p["name"] for p in scoped}


@pytest.mark.asyncio
async def test_inactive_policies_never_returned(db_session):
    p = Policy(
        id=uuid.uuid4(), name="test_scoped_inactive",
        condition={}, active=False,
        principal_type="agent", principal_id="agent-a",
        action_tool=None, resource_system=None, effect="deny", cedar_text="//v",
    )
    db_session.add(p)
    await db_session.flush()

    scoped = await get_scoped_policies(
        db_session, agent_name="agent-a", agent_groups=[],
        tool_name="http_post", system="unknown",
    )
    assert "test_scoped_inactive" not in {p["name"] for p in scoped}


@pytest.mark.asyncio
async def test_scoped_query_includes_policies_with_no_principal(db_session):
    """A NULL principal means "applies to every agent". Without an IS NULL branch
    in the pre-filter, every default policy in policies.yaml silently matches no
    agent at all -- the engine would evaluate an empty policy set and allow
    everything."""
    p = Policy(
        id=uuid.uuid4(), name="test_scoped_unscoped", condition={}, active=True,
        principal_type=None, principal_id=None,
        action_tool=None, resource_system=None, effect="deny", cedar_text="//u",
    )
    db_session.add(p)
    await db_session.flush()

    for agent in ("agent-a", "some-other-agent"):
        scoped = await get_scoped_policies(
            db_session, agent_name=agent, agent_groups=[],
            tool_name="anything", system="unknown",
        )
        assert "test_scoped_unscoped" in {x["name"] for x in scoped}, agent
