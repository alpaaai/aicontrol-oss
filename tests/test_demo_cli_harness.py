"""The CLI harness must drive a scenario purely over real HTTP -- no
ASGITransport, no direct DB reads for the enforcement steps themselves. It
runs against the same FastAPI app as everything else in the test suite, but
via a real httpx.AsyncClient constructed with a base_url, which is the shape
a real integrated agent's HTTP client takes (transport swapped for the test
app in this one place only, so the suite doesn't need a live uvicorn process).
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from scripts.demos.harness import DemoHarness


@pytest.fixture
def real_http_client(monkeypatch):
    """Swap only the transport, not the flow: harness.py must ask httpx for
    an AsyncClient(base_url=..., transport=...) rather than hand-rolling an
    ASGITransport client. Patches DemoHarness._make_client so the transport
    used in this test suite hits the in-process ASGI app instead of a real
    socket, while every other line of the harness still runs unmodified."""
    def _make_client(self):
        return AsyncClient(transport=ASGITransport(app=app), base_url=self.api_base)
    monkeypatch.setattr(DemoHarness, "_make_client", _make_client)


@pytest.mark.asyncio
async def test_harness_fetches_scenario_from_the_api(real_http_client, db_session):
    harness = DemoHarness(scenario="insurance")
    results = await harness.run()
    assert [r["tool_name"] for r in results] == [
        "read_claim_document", "release_payment", "db_query",
    ]


@pytest.mark.asyncio
async def test_harness_produces_real_cedar_decisions(real_http_client, db_session):
    harness = DemoHarness(scenario="insurance")
    results = await harness.run()
    payment = next(r for r in results if r["tool_name"] == "release_payment")
    assert payment["decision"] == "review"
    assert payment["policy_name"] == "review_high_value_claim_payment"


@pytest.mark.asyncio
async def test_two_runs_of_the_same_scenario_produce_identical_decisions(real_http_client, db_session):
    first = await DemoHarness(scenario="insurance").run()
    second = await DemoHarness(scenario="insurance").run()
    assert [r["decision"] for r in first] == [r["decision"] for r in second]


@pytest.mark.asyncio
async def test_unknown_scenario_raises(real_http_client, db_session):
    with pytest.raises(Exception):
        await DemoHarness(scenario="gtm").run()
