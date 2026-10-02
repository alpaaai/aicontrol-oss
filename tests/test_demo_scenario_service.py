import pytest
from app.services.demo_scenario_service import list_scenarios, get_scenario, all_scenario_ids

EXPECTED_IDS = {
    "insurance", "healthcare", "itsm", "lending",
    "support", "revops", "ev_manufacturing", "automotive_product_planning", "automotive_mcp_orchestration",
    "manufacturing_field_quality",
}


def test_all_scenario_ids_are_exactly_the_ten_approved():
    assert set(all_scenario_ids()) == EXPECTED_IDS


def test_list_scenarios_returns_summaries_without_steps():
    summaries = list_scenarios()
    assert len(summaries) == 10
    for s in summaries:
        assert not hasattr(s, "steps")
        assert s.id in EXPECTED_IDS


def test_get_scenario_returns_full_detail():
    scenario = get_scenario("insurance")
    assert scenario.agent_name == "claims-adjuster"
    assert scenario.agent_id == "10000000-0000-0000-0000-000000000001"
    assert 2 <= len(scenario.steps) <= 3
    for step in scenario.steps:
        assert step.expected in ("allow", "deny", "review")


def test_get_unknown_scenario_raises_key_error():
    with pytest.raises(KeyError):
        get_scenario("gtm")


def test_every_scenario_file_has_two_or_three_steps():
    for scenario_id in all_scenario_ids():
        scenario = get_scenario(scenario_id)
        assert 2 <= len(scenario.steps) <= 3, scenario_id


def test_manufacturing_field_quality_scenario_shape():
    scenario = get_scenario("manufacturing_field_quality")
    assert scenario.agent_name == "field-quality-agent"
    assert scenario.agent_id == "10000000-0000-0000-0000-000000000007"
    assert [s.expected for s in scenario.steps] == ["allow", "review", "deny"]
    assert [s.tool_name for s in scenario.steps] == [
        "query_field_signals", "release_installation_guidance", "apply_concession_release",
    ]
    assert {s.tool_name for s in scenario.steps} <= set(scenario.approved_tools)
