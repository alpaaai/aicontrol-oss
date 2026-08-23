"""Compile scope columns + condition JSONB into Cedar source."""
import uuid

from app.models.schemas import Policy
from app.services.policy_compiler import NUMERIC_SCALE, compile_condition, compile_policy


def _policy(**kw) -> Policy:
    defaults = dict(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="p", condition={},
        principal_type="agent", principal_id="claims-adjuster",
        action_tool="release_payment", resource_system="guidewire", effect="deny",
    )
    defaults.update(kw)
    return Policy(**defaults)


def test_full_scope_compiles_to_annotated_forbid():
    src = compile_policy(_policy(condition={"numeric_conditions": {"amount": {"gt": 50000}}}))
    assert '@id("11111111-1111-1111-1111-111111111111")' in src
    assert '@effect("deny")' in src
    assert 'principal == Agent::"claims-adjuster"' in src
    assert 'action == Action::"release_payment"' in src
    assert 'resource == System::"guidewire"' in src
    assert f"context.amount > {50000 * NUMERIC_SCALE}" in src
    assert src.rstrip().endswith(";")


def test_group_principal_uses_in():
    src = compile_policy(_policy(principal_type="group", principal_id="finance"))
    assert 'principal in AgentGroup::"finance"' in src


def test_null_action_and_resource_are_unconstrained():
    src = compile_policy(_policy(action_tool=None, resource_system=None, condition={}))
    assert "action," in src
    assert "resource" in src
    assert "Action::" not in src
    assert "System::" not in src


def test_review_effect_is_annotated():
    src = compile_policy(_policy(effect="review"))
    assert '@effect("review")' in src
    assert src.strip().startswith("@id")


def test_empty_condition_emits_no_when_clause():
    src = compile_policy(_policy(condition={}))
    assert "when" not in src


def test_tool_name_contains_becomes_like():
    out = compile_condition({"tool_name_contains": ["credit", "bulk"]})
    assert '(context.tool_name like "*credit*" || context.tool_name like "*bulk*")' in out
    assert out.startswith("(context has ") or "context has" not in out


def test_numeric_operators():
    out = compile_condition({"numeric_conditions": {"amount": {"gte": 100}}}) == "(context.amount >= 100)"
    out = compile_condition({"numeric_conditions": {"rows": {"lt": 5}}})
    assert f"(context.rows < {5 * NUMERIC_SCALE})" in out
    assert out.startswith("(context has ") or "context has" not in out


def test_rate_limit_reads_call_count():
    out = compile_condition({"rate_limit": {"max_calls": 5}})
    assert f"(context.call_count >= {5 * NUMERIC_SCALE})" in out
    assert out.startswith("(context has ") or "context has" not in out


def test_time_window():
    out = compile_condition({"time_conditions": {"hours": [6, 20]}})
    assert f"(context.hour < {6 * NUMERIC_SCALE} || context.hour > {20 * NUMERIC_SCALE})" in out
    assert out.startswith("(context has ") or "context has" not in out


def test_parameter_match_quotes_strings_and_not_numbers():
    out = compile_condition({"parameter_match": {"region": "eu"}}) == '(context.region == "eu")'
    out = compile_condition({"parameter_match": {"tier": 3}})
    assert f"(context.tier == {3 * NUMERIC_SCALE})" in out
    assert out.startswith("(context has ") or "context has" not in out


def test_all_of_joins_with_and():
    out = compile_condition({"all_of": [
        {"numeric_conditions": {"amount": {"gt": 100}}},
        {"parameter_match": {"region": "eu"}},
    ]})
    assert " && " in out
    assert f"context.amount > {100 * NUMERIC_SCALE}" in out
    assert 'context.region == "eu"' in out
    assert "context has amount" in out and "context has region" in out


def test_any_of_joins_with_or():
    out = compile_condition({"any_of": [
        {"numeric_conditions": {"amount": {"gt": 100}}},
        {"numeric_conditions": {"rows": {"gt": 10}}},
    ]})
    assert " || " in out
    assert f"context.amount > {100 * NUMERIC_SCALE}" in out and f"context.rows > {10 * NUMERIC_SCALE}" in out


def test_multiple_top_level_keys_join_with_and():
    out = compile_condition({
        "numeric_conditions": {"amount": {"gt": 100}},
        "parameter_match": {"region": "eu"},
    })
    assert "&&" in out and f"context.amount > {100 * NUMERIC_SCALE}" in out and 'context.region == "eu"' in out

import pytest
from cedarpy import PolicySet


@pytest.mark.parametrize("condition", [
    {},
    {"numeric_conditions": {"amount": {"gt": 50000}}},
    {"tool_name_contains": ["credit"]},
    {"parameter_match": {"region": "eu"}},
    {"rate_limit": {"max_calls": 5}},
    {"time_conditions": {"hours": [6, 20]}},
    {"token_budget": {"max_tokens": 100000}},
    {"all_of": [{"numeric_conditions": {"amount": {"gt": 1}}},
                {"parameter_match": {"region": "eu"}}]},
    {"any_of": [{"numeric_conditions": {"amount": {"gt": 1}}},
                {"numeric_conditions": {"rows": {"gt": 2}}}]},
])
def test_every_compiled_policy_parses_as_cedar(condition):
    src = compile_policy(_policy(condition=condition))
    PolicySet.from_str(src + "\npermit (principal, action, resource);")


# ── Real base.rego semantics the C4 table did not cover ──────────────────────

def test_tool_name_in_is_exact_not_substring():
    """blocked_tools and tool_aliases are exact matches in base.rego. Using
    tool_name_contains for them would broaden a denylist: blocking
    delete_database would also block delete_database_v2."""
    out = compile_condition({"tool_name_in": ["delete_database", "drop_table"]})
    assert '(context.tool_name == "delete_database" || context.tool_name == "drop_table")' in out
    assert out.startswith("(context has ") or "context has" not in out


def test_parameter_match_globs_only_when_wildcarded():
    out = compile_condition({"parameter_match": {"patient_id": "PT-2024-09*"}})
    assert '(context.patient_id like "PT-2024-09*")' in out
    assert out.startswith("(context has ") or "context has" not in out
    out = compile_condition({"parameter_match": {"patient_id": "PT-1"}})
    assert '(context.patient_id == "PT-1")' in out
    assert out.startswith("(context has ") or "context has" not in out


def test_bare_wildcard_stays_an_equality_test():
    """base.rego treats a bare * as a literal, not a glob. Emitting `like "*"`
    would match every value instead of the literal asterisk the injection sends."""
    out = compile_condition({"parameter_match": {"insured_id": "*"}})
    assert '(context.insured_id == "*")' in out
    assert out.startswith("(context has ") or "context has" not in out


def test_deny_days():
    out = compile_condition({"time_conditions": {"deny_days": [5, 6]}})
    assert f"((context.day_of_week == {5 * NUMERIC_SCALE} || context.day_of_week == {6 * NUMERIC_SCALE}))" in out
    assert out.startswith("(context has ") or "context has" not in out


def test_deny_hours_is_inclusive_from_exclusive_to():
    out = compile_condition({"time_conditions": {"deny_hours": {"from": 9, "to": 17}}})
    assert f"((context.hour >= {9 * NUMERIC_SCALE} && context.hour < {17 * NUMERIC_SCALE}))" in out
    assert out.startswith("(context has ") or "context has" not in out


def test_deny_days_and_deny_hours_are_anded():
    """base.rego was deliberately changed from OR to AND here: a policy meaning
    'weekends, 9-5' must not deny all day Saturday and 9-5 every weekday."""
    out = compile_condition({"time_conditions": {"deny_days": [5, 6], "deny_hours": {"from": 9, "to": 17}}})
    assert "&&" in out
    assert f"day_of_week == {5 * NUMERIC_SCALE}" in out and f"hour >= {9 * NUMERIC_SCALE}" in out


@pytest.mark.parametrize("condition", [
    {"tool_name_in": ["delete_database", "drop_table"]},
    {"parameter_match": {"patient_id": "PT-2024-09*"}},
    {"parameter_match": {"insured_id": "*"}},
    {"time_conditions": {"deny_days": [5, 6]}},
    {"time_conditions": {"deny_hours": {"from": 9, "to": 17}}},
    {"time_conditions": {"deny_days": [5, 6], "deny_hours": {"from": 9, "to": 17}}},
])
def test_extended_conditions_parse_as_cedar(condition):
    src = compile_policy(_policy(condition=condition))
    PolicySet.from_str(src + "\npermit (principal, action, resource);")
