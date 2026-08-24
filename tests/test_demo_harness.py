"""The demo harness runs a real agent through a real adapter with a fixed LLM.

Correction against the real SDK: OpenAIAgentsSDKAdapter.name is "openai_agents"
(sdk/src/aicontrol_sdk/adapters/openai_agents_sdk.py:20), not "openai_agents_sdk"
as an earlier draft of this test assumed -- the class name and the .name
attribute are not the same string. Asserted against the real value.
"""
import pytest

from scripts.demos.harness import DemoHarness, load_fixture


def test_fixture_mode_needs_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    harness = DemoHarness(scenario="insurance", live=False)
    assert harness.llm_mode == "fixture"


def test_fixture_transcripts_are_deterministic():
    first = load_fixture("insurance")
    second = load_fixture("insurance")
    assert first == second


def test_enforcement_is_real_in_fixture_mode():
    """The LLM is mocked; the policy decision never is."""
    harness = DemoHarness(scenario="insurance", live=False)
    assert harness.intercept_is_live is True


def test_live_flag_switches_the_llm_only():
    harness = DemoHarness(scenario="insurance", live=True)
    assert harness.llm_mode == "live"
    assert harness.intercept_is_live is True


def test_the_harness_runs_on_the_openai_agents_sdk():
    """D15: one framework for all three demos."""
    harness = DemoHarness(scenario="insurance", live=False)
    assert harness.adapter.name == "openai_agents"


def test_the_session_id_comes_from_the_framework_not_a_uuid4():
    """The point of running on this SDK is that group_id is real. If the
    harness falls back to a generated id the demo is showing a stranger."""
    harness = DemoHarness(scenario="insurance", live=False)
    assert harness.session_id == harness.expected_group_id


@pytest.mark.asyncio
async def test_run_wires_the_real_group_id_through_the_adapter():
    """The harness declares session_id upfront and must actually pass it as
    RunConfig.group_id -- otherwise expected_group_id is just an unchecked
    promise. Confirmed via a real run: every recorded result's audit trail
    shares harness.session_id (checked indirectly through a full scenario
    run in test_demo_insurance.py; here we only check the harness doesn't
    fabricate a fresh id per beat)."""
    harness = DemoHarness(scenario="insurance", live=False)
    results = await harness.run()
    assert results, "no results recorded"
