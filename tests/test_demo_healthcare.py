"""The healthcare demo denies a cross-encounter PHI access."""
import pytest

from scripts.demos.harness import DemoHarness


@pytest.mark.asyncio
async def test_cross_encounter_fetch_is_denied():
    results = await DemoHarness(scenario="healthcare", live=False).run()
    fetch = next(r for r in results if r["tool_name"] == "fetch_encounter")
    assert fetch["decision"] == "deny"
    assert fetch["policy_name"] == "deny_cross_encounter_phi_access"


@pytest.mark.asyncio
async def test_the_assigned_patient_fetch_is_allowed():
    """A demo where every call is denied proves nothing about the policy's
    scope -- the in-scope read must succeed in the same run."""
    results = await DemoHarness(scenario="healthcare", live=False).run()
    allowed = [r for r in results if r["decision"] == "allow"]
    assert allowed, "no call was allowed; the policy is over-broad"


@pytest.mark.asyncio
async def test_the_trigger_is_grounded_in_the_care_plan_read():
    results = await DemoHarness(scenario="healthcare", live=False).run()
    tools = [r["tool_name"] for r in results]
    assert tools.index("read_care_plan") < tools.index("fetch_encounter")


@pytest.mark.asyncio
async def test_the_run_carries_a_real_workflow():
    results = await DemoHarness(scenario="healthcare", live=False).run()
    assert all(r["workflow"] == "care_coordination" for r in results)


@pytest.mark.asyncio
async def test_two_runs_produce_identical_decisions():
    first = await DemoHarness(scenario="healthcare", live=False).run()
    second = await DemoHarness(scenario="healthcare", live=False).run()
    assert [r["decision"] for r in first] == [r["decision"] for r in second]
