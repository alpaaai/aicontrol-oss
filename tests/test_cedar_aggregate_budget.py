"""Agent-level aggregate budget, compiled and evaluated in-process.

Replaces test_intercept_aggregate_budget, which seeded spend into audit_events
and drove /intercept on the shared live server. Even after being rewritten in
phase 1 with a unique agent and policy per run, it stayed order-dependent for the
same reason as the temporal tests -- so the behaviour is asserted here instead,
against the engine directly.

What this proves is the point the original test existed for: a budget policy that
names no tool still denies a call to a completely different tool, because the
cap is on the agent's cumulative spend rather than on any one tool.
"""
import uuid

import pytest

from app.models.schemas import Policy
from app.services.cedar_client import evaluate, invalidate_policy_set_cache
from app.services.policy_compiler import compile_policy

CAP_USD = 100


async def _decide(condition: dict, tool_name: str, context: dict) -> str:
    row = Policy(
        id=uuid.uuid4(),
        name="aggregate_budget_probe",
        condition=condition,
        principal_type="agent",
        principal_id="spendy-agent",
        action_tool=None,          # deliberately unbound: any tool
        resource_system=None,
        effect="deny",
    )
    invalidate_policy_set_cache()
    result = await evaluate(
        agent_name="spendy-agent",
        agent_groups=[],
        tool_name=tool_name,
        system="unknown",
        context={"tool_name": tool_name, **context},
        policies=[{
            "id": str(row.id), "name": row.name, "effect": "deny",
            "cedar_text": compile_policy(row),
        }],
    )
    return result["decision"]


# The standalone budget condition exists in two shapes: flat, with its fields at
# the top level, and nested under a "budget" key. Both must enforce identically.
CONDITIONS = {
    "flat": {"scope": "agent", "max_cost_usd": CAP_USD, "window": "session", "on_exceed": "deny"},
    "nested": {"budget": {"scope": "agent", "max_cost_usd": CAP_USD}},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("shape", sorted(CONDITIONS))
async def test_prior_spend_over_the_cap_denies_a_different_tool(shape):
    decision = await _decide(
        CONDITIONS[shape], "a_completely_different_tool",
        {"agent_cumulative_cost_usd": 150.0},
    )
    assert decision == "deny"


@pytest.mark.asyncio
@pytest.mark.parametrize("shape", sorted(CONDITIONS))
async def test_spend_under_the_cap_allows(shape):
    decision = await _decide(
        CONDITIONS[shape], "a_completely_different_tool",
        {"agent_cumulative_cost_usd": 10.0},
    )
    assert decision == "allow"


@pytest.mark.asyncio
async def test_the_cap_is_exclusive():
    """The check runs against spend so far, before this call's own cost is added,
    so a total exactly on the cap has not yet exceeded it."""
    decision = await _decide(
        CONDITIONS["flat"], "any_tool", {"agent_cumulative_cost_usd": float(CAP_USD)}
    )
    assert decision == "allow"


@pytest.mark.asyncio
async def test_fractional_cents_are_not_truncated():
    """cost_usd is Numeric(10,6). Cedar has no float type, so both sides are
    scaled to integers -- a naive truncation would read 100.50 as 100 and let it
    pass a cap of 100."""
    decision = await _decide(
        CONDITIONS["flat"], "any_tool", {"agent_cumulative_cost_usd": 100.50}
    )
    assert decision == "deny"


@pytest.mark.asyncio
async def test_an_org_scoped_cap_reads_the_org_totals():
    decision = await _decide(
        {"budget": {"scope": "org", "max_cost_usd": CAP_USD}}, "any_tool",
        {"org_cumulative_cost_usd": 150.0, "agent_cumulative_cost_usd": 0.0},
    )
    assert decision == "deny"


@pytest.mark.asyncio
async def test_a_token_cap_denies_on_cumulative_tokens():
    decision = await _decide(
        {"budget": {"scope": "agent", "max_tokens": 100_000}}, "any_tool",
        {"agent_cumulative_tokens": 150_000},
    )
    assert decision == "deny"
