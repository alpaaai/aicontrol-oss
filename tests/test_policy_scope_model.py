"""Policy scope columns — the Cedar binding primitive."""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.schemas import Policy


@pytest.mark.asyncio
async def test_policy_carries_explicit_scope(db_session):
    p = Policy(
        id=uuid.uuid4(),
        name="test_scope_policy",
        condition={},
        principal_type="agent",
        principal_id="claims-adjuster",
        action_tool="release_payment",
        resource_system="guidewire",
        effect="review",
    )
    db_session.add(p)
    await db_session.flush()

    loaded = (await db_session.execute(
        select(Policy).where(Policy.name == "test_scope_policy")
    )).scalar_one()

    assert loaded.principal_type == "agent"
    assert loaded.principal_id == "claims-adjuster"
    assert loaded.action_tool == "release_payment"
    assert loaded.resource_system == "guidewire"
    assert loaded.effect == "review"
    assert loaded.cedar_text is None


@pytest.mark.asyncio
async def test_null_action_and_resource_mean_any(db_session):
    p = Policy(
        id=uuid.uuid4(),
        name="test_scope_wildcard",
        condition={},
        principal_type="group",
        principal_id="finance",
        effect="deny",
    )
    db_session.add(p)
    await db_session.flush()

    loaded = (await db_session.execute(
        select(Policy).where(Policy.name == "test_scope_wildcard")
    )).scalar_one()

    assert loaded.action_tool is None
    assert loaded.resource_system is None
    assert loaded.principal_type == "group"


@pytest.mark.asyncio
async def test_effect_is_required(db_session):
    """Task 2.8 tightened effect to NOT NULL: a policy with no effect has no
    meaning under Cedar, where every AIControl policy is a forbid that is either
    a deny or a review. principal_type/principal_id stay nullable on purpose --
    NULL principal reads as "applies to every agent"."""
    p = Policy(id=uuid.uuid4(), name="test_scope_no_effect", condition={})
    db_session.add(p)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_null_principal_means_every_agent(db_session):
    p = Policy(
        id=uuid.uuid4(),
        name="test_scope_unscoped_principal",
        condition={},
        effect="deny",
    )
    db_session.add(p)
    await db_session.flush()

    loaded = (await db_session.execute(
        select(Policy).where(Policy.name == "test_scope_unscoped_principal")
    )).scalar_one()

    assert loaded.principal_type is None
    assert loaded.principal_id is None
    assert loaded.effect == "deny"
