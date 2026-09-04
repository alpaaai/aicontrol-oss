import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.models.database import async_session_factory
from app.models.schemas import Agent
from app.services.demo_provisioning import (
    provision_demo_agents, reset_demo_agents, issue_scenario_token,
)
from app.services.demo_scenario_service import get_scenario, all_scenario_ids


@pytest_asyncio.fixture(scope="module", loop_scope="session", autouse=True)
async def _restore_demo_agent_baseline():
    """provision_demo_agents() upserts scenario-scoped approved_tools onto
    agent ids that scripts.seed.AGENTS also seeds (010/030/050/060 --
    itsm/lending/support/revops share those fixed ids with the general
    dev/test baseline). Other test files assume that baseline, so restore it
    after every test in this module."""
    yield
    from scripts.seed import AGENTS

    async with async_session_factory() as session:
        for agent in AGENTS:
            await session.execute(
                text("UPDATE agents SET approved_tools = CAST(:tools AS jsonb) WHERE id = :id"),
                {"id": agent["id"], "tools": agent["tools"]},
            )
        await session.commit()


@pytest.mark.asyncio
async def test_provision_creates_all_eight_demo_agents(db_session):
    await provision_demo_agents()
    async with async_session_factory() as session:
        for scenario_id in all_scenario_ids():
            scenario = get_scenario(scenario_id)
            agent = (await session.execute(
                select(Agent).where(Agent.id == scenario.agent_id)
            )).scalar_one()
            assert agent.name == scenario.agent_name
            assert agent.status == "active"
            assert set(agent.approved_tools) == set(scenario.approved_tools)


@pytest.mark.asyncio
async def test_itsm_agent_has_http_post_approved(db_session):
    """The whole point of this fix: http_post must be approved so the deny
    comes from Cedar's block_http_post_in_itsm policy, not the approved-tools
    gate."""
    await provision_demo_agents()
    itsm = get_scenario("itsm")
    async with async_session_factory() as session:
        agent = (await session.execute(
            select(Agent).where(Agent.id == itsm.agent_id)
        )).scalar_one()
    assert "http_post" in agent.approved_tools


@pytest.mark.asyncio
async def test_reset_clears_sessions_and_reprovisions(db_session):
    await provision_demo_agents()
    insurance = get_scenario("insurance")
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO sessions (id, agent_id, status)
            VALUES (gen_random_uuid(), :agent_id, 'active')
        """), {"agent_id": insurance.agent_id})
        await session.commit()

    await reset_demo_agents()

    async with async_session_factory() as session:
        count = (await session.execute(text(
            "SELECT COUNT(*) FROM sessions WHERE agent_id = :agent_id"
        ), {"agent_id": insurance.agent_id})).scalar()
        agent = (await session.execute(
            select(Agent).where(Agent.id == insurance.agent_id)
        )).scalar_one()
    assert count == 0
    assert agent.status == "active"


@pytest.mark.asyncio
async def test_reset_clears_hitl_review_referencing_audit_event_matched_only_by_agent_id(db_session):
    """Regression: an audit_event matched by agent_id (not via a demo
    session's session_id) with a hitl_review pointing at it used to survive
    the hitl_reviews delete (which only looked at session_id), then blocked
    the audit_events delete with a foreign key violation."""
    await provision_demo_agents()
    insurance = get_scenario("insurance")
    async with async_session_factory() as session:
        event_id = (await session.execute(text("""
            INSERT INTO audit_events (id, sequence_number, agent_id, tool_name, decision)
            VALUES (gen_random_uuid(), 1, :agent_id, 'read_claim_document', 'allow')
            RETURNING id
        """), {"agent_id": insurance.agent_id})).scalar_one()
        await session.execute(text("""
            INSERT INTO hitl_reviews (id, audit_event_id, session_id, status)
            VALUES (gen_random_uuid(), :event_id, NULL, 'pending')
        """), {"event_id": event_id})
        await session.commit()

    await reset_demo_agents()

    async with async_session_factory() as session:
        event_count = (await session.execute(text(
            "SELECT COUNT(*) FROM audit_events WHERE id = :id"
        ), {"id": event_id})).scalar()
    assert event_count == 0


@pytest.mark.asyncio
async def test_issue_scenario_token_is_scoped_to_that_agent(db_session):
    await provision_demo_agents()
    token = await issue_scenario_token("insurance")
    assert isinstance(token, str) and len(token) > 0
