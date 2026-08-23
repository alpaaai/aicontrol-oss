"""Numeric threshold enforcement, compiled and evaluated in-process.

Replaces test_policy_engine::test_numeric_gt_deny, which drove the same behaviour
through the live API and flaked roughly one full-suite run in one -- always
"expected deny, got allow", and only once ~18 files' worth of accumulated
database state sat ahead of it. Nothing here touches the shared server or the
database, so the same assertions hold in any run order.

Covers what that test covered and a little more: the gt threshold, both sides of
the boundary, the tool binding, and the two numeric spellings that exist in real
policy conditions.
"""
import uuid

import pytest

from app.models.schemas import Policy
from app.services.cedar_client import evaluate, invalidate_policy_set_cache
from app.services.policy_compiler import compile_policy

AGENT = "claims-processing-agent"
TOOL = "approve_loan"
THRESHOLD = 500_000


def _loan_limit_policy(condition: dict) -> tuple[str, dict]:
    pid = str(uuid.uuid4())
    row = Policy(
        id=uuid.UUID(pid),
        name="numeric_threshold_probe",
        condition=condition,
        principal_type=None,
        principal_id=None,
        action_tool=TOOL,
        resource_system=None,
        effect="deny",
    )
    return pid, {
        "id": pid,
        "name": row.name,
        "effect": "deny",
        "cedar_text": compile_policy(row),
    }


# Both spellings appear in real conditions: the compact object form and
# base.rego's list form. They must enforce identically.
CONDITIONS = {
    "compact": {"numeric_conditions": {"loan_amount": {"gt": THRESHOLD}}},
    "list": {"numeric_conditions": [
        {"parameter": "loan_amount", "operator": "gt", "value": THRESHOLD}
    ]},
}


async def _decide(condition: dict, tool_name: str, params: dict) -> dict:
    pid, policy = _loan_limit_policy(condition)
    invalidate_policy_set_cache()
    result = await evaluate(
        agent_name=AGENT,
        agent_groups=[],
        tool_name=tool_name,
        system="unknown",
        context={"tool_name": tool_name, **params},
        policies=[policy],
    )
    return result | {"_policy_id": pid}


@pytest.mark.asyncio
@pytest.mark.parametrize("spelling", sorted(CONDITIONS))
async def test_over_threshold_denies(spelling):
    result = await _decide(CONDITIONS[spelling], TOOL,
                           {"loan_amount": 750_000, "applicant_id": "APP-001"})
    assert result["decision"] == "deny"
    assert result["fired_policy_name"] == "numeric_threshold_probe"
    assert result["fired_policy_id"] == result["_policy_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("spelling", sorted(CONDITIONS))
async def test_under_threshold_allows(spelling):
    result = await _decide(CONDITIONS[spelling], TOOL,
                           {"loan_amount": 100_000, "applicant_id": "APP-001"})
    assert result["decision"] == "allow"
    assert result["fired_policy_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("spelling", sorted(CONDITIONS))
async def test_threshold_is_exclusive(spelling):
    """gt, not gte: a value exactly on the threshold must not fire."""
    result = await _decide(CONDITIONS[spelling], TOOL, {"loan_amount": THRESHOLD})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_other_tools_are_unaffected():
    """The policy binds one tool through action_tool, so an over-threshold value
    on a different tool must not fire it."""
    result = await _decide(CONDITIONS["compact"], "read_record",
                           {"loan_amount": 750_000})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_a_missing_parameter_does_not_fire_the_policy():
    """Cedar errors on a context attribute that is not present, and an errored
    evaluation comes back as Deny -- so without the compiler's `has` guard this
    policy would deny every approve_loan call that omitted loan_amount."""
    result = await _decide(CONDITIONS["compact"], TOOL, {"applicant_id": "APP-001"})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_a_stringified_number_still_enforces():
    """An agent that sends its parameters as strings must not slip past a numeric
    policy: Cedar is strictly typed, so "750000" would never match > 500000
    without the client's coercion."""
    result = await _decide(CONDITIONS["compact"], TOOL, {"loan_amount": "750000"})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_a_fractional_value_enforces_without_losing_precision():
    """cost-style fractional values must compare exactly. Cedar has no float
    type, so both the threshold and the context are scaled to integers; a naive
    truncation would let 500000.5 read as 500000 and escape a gt threshold."""
    result = await _decide(CONDITIONS["compact"], TOOL, {"loan_amount": 500_000.5})
    assert result["decision"] == "deny"
