"""Numeric, compound and tool-alias enforcement, compiled and evaluated in-process.

Replaces tests/test_policy_engine.py, every test of which POSTed a policy to the
shared live server and then asserted an /intercept decision. That shape is the
one phase 2 identified as order-dependent: the failures rotated between runs
("expected deny, got allow") and reproduced only with enough prior files'
database state ahead of them. Measured on this branch before the rewrite: three
clean full-suite runs then two dirty, and the untouched baseline flaked too, so
the file was flaky in itself rather than because of any change to it.

The file also coupled its own tests to each other -- several allow-path cases
asserted "allow" only because a policy an *earlier* test in the file had created
happened not to match. Here each case builds the policy it needs and evaluates
against that policy alone.

Coverage is the same or wider: every case the old file asserted is asserted
here, against the same conditions, plus the boundary each one implied.
"""
import uuid

import pytest

from app.models.schemas import Policy
from app.services.cedar_client import evaluate, invalidate_policy_set_cache
from app.services.policy_compiler import ALL_PARAMS_FIELD, compile_policy
from app.services.cedar_client import current_time_context

LOAN_AGENT = "claims-processing-agent"
SUPPORT_AGENT = "support-resolution-agent"
CLINICAL_AGENT = "clinical-documentation-agent"
INCIDENT_AGENT = "incident-response-agent"


def _policy(name: str, condition: dict, effect: str = "deny") -> tuple[str, dict]:
    """A policy row as POST /policies would store it: the tool binding lives in
    the condition, so every scope column stays NULL (see validate_policy_scope
    in app/routers/policies.py -- a condition alone is a valid policy)."""
    pid = str(uuid.uuid4())
    row = Policy(
        id=uuid.UUID(pid),
        name=name,
        condition=condition,
        principal_type=None,
        principal_id=None,
        action_tool=None,
        resource_system=None,
        effect=effect,
    )
    return pid, {"id": pid, "name": name, "effect": effect,
                 "cedar_text": compile_policy(row)}


async def _decide(condition: dict, *, agent: str, tool_name: str,
                  params: dict, name: str = "engine_probe") -> dict:
    """Evaluate one call against one policy, with the context /intercept builds."""
    pid, policy = _policy(name, condition)
    invalidate_policy_set_cache()
    result = await evaluate(
        agent_name=agent,
        agent_groups=[],
        tool_name=tool_name,
        system="unknown",
        context={
            "tool_name": tool_name,
            **params,
            ALL_PARAMS_FIELD: " ".join(str(v) for v in params.values()),
            **current_time_context(),
            "call_count": 0,
            "cumulative_tokens": 0,
            "cumulative_cost_usd": 0,
            "agent_cumulative_tokens": 0,
            "agent_cumulative_cost_usd": 0,
            "org_cumulative_tokens": 0,
            "org_cumulative_cost_usd": 0,
            "workflow": "unassigned",
        },
        policies=[policy],
    )
    return result | {"_policy_id": pid}


# ── Numeric comparison ────────────────────────────────────────────────────────

_LOAN_LIMIT = {
    "blocked_tools": ["approve_loan"],
    "numeric_conditions": [
        {"parameter": "loan_amount", "operator": "gt", "value": 500000}
    ],
}

_CREDIT_FLOOR = {
    "blocked_tools": ["approve_loan"],
    "numeric_conditions": [
        {"parameter": "credit_score", "operator": "lt", "value": 600}
    ],
}

_MULTI_NUMERIC = {
    "blocked_tools": ["approve_loan"],
    "numeric_conditions": [
        {"parameter": "loan_amount", "operator": "gt", "value": 500000},
        {"parameter": "loan_term_years", "operator": "gt", "value": 30},
    ],
}


@pytest.mark.asyncio
async def test_numeric_gt_allow_below_threshold():
    result = await _decide(_LOAN_LIMIT, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 200000, "applicant_id": "APP-002"})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_numeric_gt_deny_above_threshold():
    result = await _decide(_LOAN_LIMIT, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 750000, "applicant_id": "APP-003"})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_numeric_gt_allows_exactly_at_threshold():
    """gt, not gte -- the boundary belongs on the allow side."""
    result = await _decide(_LOAN_LIMIT, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 500000})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_numeric_lt_deny():
    result = await _decide(_CREDIT_FLOOR, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 100000, "credit_score": 520})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_numeric_lt_allows_exactly_at_floor():
    result = await _decide(_CREDIT_FLOOR, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 100000, "credit_score": 600})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_numeric_multi_condition_deny_both_match():
    result = await _decide(_MULTI_NUMERIC, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 750000, "loan_term_years": 35})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_numeric_multi_condition_allow_one_fails():
    """Multiple numeric conditions are ANDed: one satisfied is not enough."""
    result = await _decide(_MULTI_NUMERIC, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 300000, "loan_term_years": 35})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_numeric_gt_allow_with_stringified_low_number():
    """A stringified "99" must be read as 99, not treated as greater than
    500000 by cross-type ordering (the Rego behaviour this guards against)."""
    result = await _decide(_LOAN_LIMIT, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": "99", "applicant_id": "APP-STR-1"})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_numeric_lt_deny_with_stringified_number():
    """A stringified "550" must still satisfy lt 600 rather than being skipped."""
    result = await _decide(_CREDIT_FLOOR, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"credit_score": "550", "applicant_id": "APP-STR-2"})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_numeric_policy_does_not_fire_for_another_tool():
    """The tool binding is part of the condition -- an unrelated tool is allowed
    even when the numeric threshold is breached."""
    result = await _decide(_LOAN_LIMIT, agent=LOAN_AGENT, tool_name="query_lab_results",
                           params={"loan_amount": 750000})
    assert result["decision"] == "allow"


# ── Compound all_of / any_of ──────────────────────────────────────────────────

_COMPOUND_AND = {
    "blocked_tools": ["approve_loan"],
    "all_of": [
        {"numeric_conditions": [
            {"parameter": "loan_amount", "operator": "gt", "value": 500000}
        ]},
        {"parameter_match": {"applicant_type": "subprime"}},
    ],
}

_COMPOUND_OR = {
    "blocked_tools": ["fetch_account_detail"],
    "any_of": [
        {"parameter_match": {"account_id": "WILDCARD-*"}},
        {"parameter_match": {"account_id": "null"}},
    ],
}


@pytest.mark.asyncio
async def test_compound_all_of_deny_both_match():
    result = await _decide(_COMPOUND_AND, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 750000, "applicant_type": "subprime"})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_compound_all_of_allow_numeric_only():
    result = await _decide(_COMPOUND_AND, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 750000, "applicant_type": "prime"})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_compound_all_of_allow_parameter_only():
    result = await _decide(_COMPOUND_AND, agent=LOAN_AGENT, tool_name="approve_loan",
                           params={"loan_amount": 300000, "applicant_type": "subprime"})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_compound_any_of_deny_first_matches():
    result = await _decide(_COMPOUND_OR, agent=SUPPORT_AGENT,
                           tool_name="fetch_account_detail",
                           params={"account_id": "WILDCARD-ALL"})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_compound_any_of_deny_second_matches():
    result = await _decide(_COMPOUND_OR, agent=SUPPORT_AGENT,
                           tool_name="fetch_account_detail",
                           params={"account_id": "null"})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_compound_any_of_allow_neither_matches():
    result = await _decide(_COMPOUND_OR, agent=SUPPORT_AGENT,
                           tool_name="fetch_account_detail",
                           params={"account_id": "ACC-12345"})
    assert result["decision"] == "allow"


# ── Tool aliases ──────────────────────────────────────────────────────────────

_PHI_FAMILY = {
    "blocked_tools": ["read_patient_record"],
    "tool_aliases": ["queryPatientRecord", "get_patient_data"],
    "parameter_match": {"patient_id": "PT-2024-09*"},
}

_ALL_HTTP = {
    "blocked_tools": ["http_post"],
    "tool_aliases": ["http_get", "http_request", "webhook", "webhook_call"],
}


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["queryPatientRecord", "get_patient_data"])
async def test_alias_deny_on_aliased_name(tool_name):
    """An alias extends the denylist rather than being ANDed with it."""
    result = await _decide(_PHI_FAMILY, agent=CLINICAL_AGENT, tool_name=tool_name,
                           params={"patient_id": "PT-2024-098234"})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_alias_deny_on_primary_name():
    result = await _decide(_PHI_FAMILY, agent=CLINICAL_AGENT,
                           tool_name="read_patient_record",
                           params={"patient_id": "PT-2024-098234"})
    assert result["decision"] == "deny"


@pytest.mark.asyncio
async def test_alias_allow_unrelated_tool():
    result = await _decide(_PHI_FAMILY, agent=CLINICAL_AGENT,
                           tool_name="query_lab_results",
                           params={"patient_id": "PT-2024-098234"})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_alias_allow_when_the_parameter_does_not_match():
    """The alias list widens the tools; it does not drop the other conditions."""
    result = await _decide(_PHI_FAMILY, agent=CLINICAL_AGENT,
                           tool_name="queryPatientRecord",
                           params={"patient_id": "PT-2019-000001"})
    assert result["decision"] == "allow"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name",
    ["http_post", "http_get", "http_request", "webhook", "webhook_call"],
)
async def test_alias_global_deny_all_http_variants(tool_name):
    result = await _decide(_ALL_HTTP, agent=INCIDENT_AGENT, tool_name=tool_name,
                           params={"url": "https://external.example.com"})
    assert result["decision"] == "deny", f"expected deny for tool: {tool_name}"
