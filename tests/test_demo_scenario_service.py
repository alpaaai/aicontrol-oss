import pytest
from app.services.demo_scenario_service import list_scenarios, get_scenario, all_scenario_ids

EXPECTED_IDS = {
    "insurance", "healthcare", "itsm", "lending",
    "support", "revops", "lucid_motors", "toyota_europe",
}


def test_all_scenario_ids_are_exactly_the_eight_approved():
    assert set(all_scenario_ids()) == EXPECTED_IDS


def test_list_scenarios_returns_summaries_without_steps():
    summaries = list_scenarios()
    assert len(summaries) == 8
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
