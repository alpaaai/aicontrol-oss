"""Schema validation for scripts/demos/scenarios.py — the single source of
truth for all demo scenario data. Every scenario must declare a known kind
and the fields that kind's engine run-function depends on."""
from scripts.demos.scenarios import SCENARIOS

INTERCEPT_SCENARIOS = {"lending", "healthcare", "itsm", "manufacturing", "revops", "support", "insurance"}
KNOWN_KINDS = {"intercept", "admission_scan", "mcp_gateway"}


def test_scenario_keys_match_expected_set():
    assert set(SCENARIOS.keys()) == INTERCEPT_SCENARIOS | {"admission_scanning", "mcp_gateway"}


def test_every_scenario_has_a_known_kind():
    for name, scenario in SCENARIOS.items():
        assert scenario["kind"] in KNOWN_KINDS, f"{name} has unknown kind {scenario.get('kind')!r}"


def test_every_scenario_has_name_and_description():
    for name, scenario in SCENARIOS.items():
        assert isinstance(scenario["name"], str) and scenario["name"]
        assert isinstance(scenario["description"], str) and scenario["description"]


def test_intercept_scenarios_have_required_fields():
    for name in INTERCEPT_SCENARIOS:
        scenario = SCENARIOS[name]
        assert scenario["kind"] == "intercept"
        assert scenario["agent_id"].count("-") == 4  # UUID shape
        assert scenario["agent_name"]
        assert isinstance(scenario["tool_calls"], list) and scenario["tool_calls"]
        for call in scenario["tool_calls"]:
            assert call["tool_name"]
            assert isinstance(call["tool_parameters"], dict)
            assert call["label"]
            assert call["expected"] in ("allow", "deny", "review")


def test_insurance_uses_policy_name_for_deny_detail():
    # Insurance is the one scenario whose deny line reads a distinct API field
    # (policy_name) instead of reason — preserved from the original
    # demo_insurance.py behavior, not a new feature.
    assert SCENARIOS["insurance"]["deny_detail_field"] == "policy_name"


def test_lending_calls_have_v2_feature_badges():
    calls_with_badge = [c for c in SCENARIOS["lending"]["tool_calls"] if c.get("v2_feature")]
    assert {c["v2_feature"] for c in calls_with_badge} == {"rate_limit", "approved_tools"}


def test_insurance_payment_call_has_review_note():
    payment_call = next(c for c in SCENARIOS["insurance"]["tool_calls"] if c["tool_name"] == "process_claim_payment")
    assert payment_call["review_note"] == "Routed to senior adjuster via Slack for approval"


def test_admission_scanning_steps_have_required_fields():
    scenario = SCENARIOS["admission_scanning"]
    assert scenario["kind"] == "admission_scan"
    for step in scenario["steps"]:
        assert step["kind"] in ("skill_scan", "mcp_enroll")
        assert step["label"]
        assert step["narrative"]
        assert step["insight"]
        if step["kind"] == "skill_scan":
            assert step["target_ref"]
        else:
            assert step["name"]
            assert step["base_url"]


def test_mcp_gateway_has_setup_fields_and_steps():
    scenario = SCENARIOS["mcp_gateway"]
    assert scenario["kind"] == "mcp_gateway"
    assert scenario["server_name"]
    assert scenario["downstream_base_url"]
    assert isinstance(scenario["approved_tools"], list)
    for step in scenario["steps"]:
        assert step["method"] in ("tools/list", "call_tool")
        assert isinstance(step["body"], dict)
        assert step["label"]
        assert step["narrative"]
        assert step["insight"]
