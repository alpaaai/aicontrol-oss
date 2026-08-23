"""Schema validation for scripts/demos/scenarios.py — the single source of
truth for all demo scenario data. Every scenario must declare a known kind
and the fields that kind's engine run-function depends on."""
from scripts.demos.scenarios import SCENARIOS

INTERCEPT_SCENARIOS = {"healthcare", "revops", "insurance"}
KNOWN_KINDS = {"intercept"}


def test_scenario_keys_match_expected_set():
    assert set(SCENARIOS.keys()) == INTERCEPT_SCENARIOS


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


def test_insurance_payment_call_has_review_note():
    payment_call = next(c for c in SCENARIOS["insurance"]["tool_calls"] if c["tool_name"] == "process_claim_payment")
    assert payment_call["review_note"] == "Routed to senior adjuster via Slack for approval"


