"""Every demo scenario's steps must produce their expected decision through a
real /intercept call against real Cedar policy evaluation -- this is the
guarantee the whole unification effort exists to make true. One parametrized
test walks all 8 scenarios; a couple of named tests pin down the two
specific defects the design spec called out by name.
"""
import uuid

import pytest

from app.services.demo_provisioning import provision_demo_agents, issue_scenario_token
from app.services.demo_scenario_service import all_scenario_ids, get_scenario


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id", all_scenario_ids())
async def test_scenario_steps_produce_their_expected_decision(client, scenario_id, db_session):
    await provision_demo_agents()
    scenario = get_scenario(scenario_id)
    token = await issue_scenario_token(scenario_id)
    session_id = str(uuid.uuid4())

    for i, step in enumerate(scenario.steps, start=1):
        resp = await client.post(
            "/intercept",
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
        "/intercept",
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
        "/intercept",
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
