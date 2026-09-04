"""Demo agent provisioning: derives the demo agent roster from the canonical
scenario files (app/demo_scenarios/*.json) instead of a hand-maintained list,
so there is exactly one place that says which agents the demo needs.

Provisioning is exempt from the "real HTTP only" rule (see the design spec)
-- it's not part of the enforcement demonstration. The CLI calls these
functions directly, in-process; app/routers/demo.py wraps them for the
browser, which cannot call Python directly.
"""
import json

from sqlalchemy import text

from app.core.auth import create_token, hash_token
from app.models.database import async_session_factory
from app.services.demo_scenario_service import all_scenario_ids, get_scenario


async def provision_demo_agents() -> None:
    async with async_session_factory() as session:
        for scenario_id in all_scenario_ids():
            scenario = get_scenario(scenario_id)
            await session.execute(text("""
                INSERT INTO agents (id, name, owner, status, approved_tools, governance_mode)
                VALUES (CAST(:id AS uuid), :name, :owner, 'active', CAST(:tools AS jsonb), 'govern')
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    owner = EXCLUDED.owner,
                    status = 'active',
                    approved_tools = EXCLUDED.approved_tools,
                    governance_mode = 'govern'
            """), {
                "id": scenario.agent_id,
                "name": scenario.agent_name,
                "owner": scenario.owner,
                "tools": json.dumps(scenario.approved_tools),
            })
        await session.commit()


async def reset_demo_agents() -> None:
    agent_ids = [get_scenario(sid).agent_id for sid in all_scenario_ids()]
    async with async_session_factory() as session:
        await session.execute(text(
            "DELETE FROM hitl_reviews WHERE audit_event_id IN "
            "(SELECT id FROM audit_events WHERE agent_id = ANY(:ids) OR session_id IN "
            "(SELECT id FROM sessions WHERE agent_id = ANY(:ids)))"
        ), {"ids": agent_ids})
        await session.execute(text(
            "DELETE FROM audit_events WHERE agent_id = ANY(:ids) OR session_id IN "
            "(SELECT id FROM sessions WHERE agent_id = ANY(:ids))"
        ), {"ids": agent_ids})
        await session.execute(text(
            "DELETE FROM sessions WHERE agent_id = ANY(:ids)"
        ), {"ids": agent_ids})
        await session.commit()
    await provision_demo_agents()


async def issue_scenario_token(scenario_id: str) -> str:
    """Issue a fresh agent-scoped token for one scenario's agent. Raw JWT,
    never persisted anywhere but the returned string and its hash."""
    scenario = get_scenario(scenario_id)
    token = create_token(role="agent", description=f"demo:{scenario_id}")
    async with async_session_factory() as session:
        await session.execute(text("""
            INSERT INTO api_tokens (id, token_hash, role, description, agent_id, revoked)
            VALUES (gen_random_uuid(), :hash, 'agent', :desc, CAST(:agent_id AS uuid), false)
        """), {
            "hash": hash_token(token),
            "desc": f"demo:{scenario_id}",
            "agent_id": scenario.agent_id,
        })
        await session.commit()
    return token


async def issue_demo_token() -> str:
    """Issue a fresh unscoped (agent_id = NULL) token for the browser demo
    page: it drives /intercept calls across all 8 scenario agents in one
    session, so it must not be bound to any single agent_id -- /intercept
    only enforces agent-token scoping when the token's agent_id is set."""
    token = create_token(role="agent", description="demo:shared")
    async with async_session_factory() as session:
        await session.execute(text(
            "DELETE FROM api_tokens WHERE description = 'demo:shared'"
        ))
        await session.execute(text("""
            INSERT INTO api_tokens (id, token_hash, role, description, agent_id, revoked)
            VALUES (gen_random_uuid(), :hash, 'agent', 'demo:shared', NULL, false)
        """), {"hash": hash_token(token)})
        await session.commit()
    return token
