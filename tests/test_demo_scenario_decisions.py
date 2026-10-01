"""Every demo scenario's steps must produce their expected decision through a
real /demo/call_tool call against real Cedar policy evaluation -- this is the
guarantee the whole unification effort exists to make true. One parametrized
test walks all 8 scenarios; a couple of named tests pin down the two
specific defects the design spec called out by name.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.services.demo_provisioning import provision_demo_agents, issue_scenario_token
from app.services.demo_scenario_service import all_scenario_ids, get_scenario

pytestmark = pytest.mark.usefixtures("_require_demo_mode_on_server")


@pytest_asyncio.fixture(scope="module", loop_scope="session", autouse=True)
async def _enterprise_license_for_demo():
    """Several scenarios' steps expect `review` -- app/services/governance_engine.py
    fails that closed to `deny` on a community-tier license
    (review_requires_business_license), matching how the demo is actually
    licensed in AIControl's own sales-demo environment (config.py: DEMO_MODE
    "AIControl's own sales-demo environment sets this to true"). Without
    this, the parametrized test below can't reproduce what the real demo
    shows. org_settings is treated suite-wide as a single-row table (see
    test_license_gate.py's _set_org_settings/_restore_org_settings) --
    DELETE-all-then-restore, matching that convention, rather than a
    name-filtered row, so this can't collide with another test's row via
    license_gate's unordered `select(...).limit(1)`.
    """
    from app.models.database import async_session_factory

    async with async_session_factory() as db:
        saved = await db.execute(text("SELECT id, org_name, timezone FROM org_settings"))
        existing = saved.fetchall()
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(text(
            "INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at, license_plan) "
            "VALUES (gen_random_uuid(), 'pytest-demo-org', 'UTC', now(), now(), 'enterprise')"
        ))
        await db.commit()
    yield
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM org_settings"))
        for row in existing:
            await db.execute(
                text("""
                    INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at)
                    VALUES (:id, :name, :tz, now(), now())
                    ON CONFLICT DO NOTHING
                """),
                {"id": str(row[0]), "name": row[1], "tz": row[2]},
            )
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id", all_scenario_ids())
async def test_scenario_steps_produce_their_expected_decision(client, scenario_id, db_session):
    await provision_demo_agents()
    scenario = get_scenario(scenario_id)
    token = await issue_scenario_token(scenario_id)
    session_id = str(uuid.uuid4())

    for i, step in enumerate(scenario.steps, start=1):
        resp = await client.post(
            "/demo/call_tool",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "session_id": session_id,
                "agent_id": scenario.agent_id,
                "agent_name": scenario.agent_name,
                "tool_name": step.tool_name,
                "tool_parameters": step.tool_parameters,
                "sequence_number": i,
                "workflow": scenario.workflow,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["decision"] == step.expected, (
            f"{scenario_id} step {i} ({step.tool_name}): "
            f"expected {step.expected}, got {resp.json()}"
        )


@pytest.mark.asyncio
async def test_itsm_deny_comes_from_cedar_not_the_approved_tools_gate(client, db_session):
    """The exact defect named in the design spec: http_post must be in the
    agent's approved_tools so a real Cedar policy -- not the approved-tools
    gate -- is what produces the deny. The firing policy is the shipped
    global block_unapproved_outbound_http, not itsm.yaml's
    block_http_post_in_itsm: that demo-seed policy duplicated the shipped
    one exactly (same unscoped principal/system) and was deactivated rather
    than left to silently never fire behind it."""
    await provision_demo_agents()
    scenario = get_scenario("itsm")
    token = await issue_scenario_token("itsm")
    http_post_step = next(s for s in scenario.steps if s.tool_name == "http_post")

    resp = await client.post(
        "/demo/call_tool",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": str(uuid.uuid4()),
            "agent_id": scenario.agent_id,
            "agent_name": scenario.agent_name,
            "tool_name": "http_post",
            "tool_parameters": http_post_step.tool_parameters,
            "sequence_number": 1,
            "workflow": scenario.workflow,
        },
    )
    assert resp.json()["decision"] == "deny"
    assert resp.json().get("policy_name") == "block_unapproved_outbound_http"


@pytest.mark.asyncio
async def test_insurance_review_matches_the_real_active_policy(client, db_session):
    """The exact defect named in the design spec: the amount, tool, and agent
    must match review_high_value_claim_payment's actual $50,000 threshold on
    release_payment for claims-adjuster -- not the old $5,000/process_claim_payment
    /insurance-claims-agent mismatch."""
    await provision_demo_agents()
    scenario = get_scenario("insurance")
    token = await issue_scenario_token("insurance")
    payment_step = next(s for s in scenario.steps if s.tool_name == "release_payment")
    assert payment_step.tool_parameters["amount"] > 50000

    resp = await client.post(
        "/demo/call_tool",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": str(uuid.uuid4()),
            "agent_id": scenario.agent_id,
            "agent_name": scenario.agent_name,
            "tool_name": "release_payment",
            "tool_parameters": payment_step.tool_parameters,
            "sequence_number": 1,
            "workflow": scenario.workflow,
        },
    )
    assert resp.json()["decision"] == "review"
    assert resp.json().get("policy_name") == "review_high_value_claim_payment"
