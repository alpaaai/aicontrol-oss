"""The GTM demo denies an unscoped CRM export."""
import pytest

from scripts.demos.harness import DemoHarness


@pytest.mark.asyncio
async def test_bulk_crm_query_is_denied():
    results = await DemoHarness(scenario="gtm", live=False).run()
    query = next(
        r for r in results
        if r["tool_name"] == "salesforce_query" and r["decision"] == "deny"
    )
    assert query["policy_name"] == "deny_unscoped_crm_query"


@pytest.mark.asyncio
async def test_the_scoped_segment_query_is_allowed():
    """The agent's legitimate work must still run -- otherwise the policy
    reads as a block on the tool rather than on the scope."""
    results = await DemoHarness(scenario="gtm", live=False).run()
    allowed = [
        r for r in results
        if r["tool_name"] == "salesforce_query" and r["decision"] == "allow"
    ]
    assert allowed, "the in-scope segment query was denied too"


@pytest.mark.asyncio
async def test_the_trigger_is_a_misread_personalisation_instruction():
    results = await DemoHarness(scenario="gtm", live=False).run()
    tools = [r["tool_name"] for r in results]
    assert tools.index("read_campaign_brief") < tools.index("salesforce_query")


@pytest.mark.asyncio
async def test_the_run_carries_a_real_workflow():
    results = await DemoHarness(scenario="gtm", live=False).run()
    assert all(r["workflow"] == "sales_outreach" for r in results)


@pytest.mark.asyncio
async def test_two_runs_produce_identical_decisions():
    first = await DemoHarness(scenario="gtm", live=False).run()
    second = await DemoHarness(scenario="gtm", live=False).run()
    assert [r["decision"] for r in first] == [r["decision"] for r in second]
