"""The insurance demo produces its two beats deterministically.

Correction against the real schema: HITLReview has no reviewed_by column --
the approver name lands on `reviewer` (app/models/schemas.py:156). Asserted
against the real field.
"""
import pytest

from scripts.demos.harness import DemoHarness


@pytest.mark.asyncio
async def test_high_value_settlement_is_held_for_review():
    harness = DemoHarness(scenario="insurance", live=False)
    results = await harness.run()
    payment = next(r for r in results if r["tool_name"] == "release_payment")
    assert payment["decision"] == "review"
    assert payment["policy_name"] == "review_high_value_claim_payment"


@pytest.mark.asyncio
async def test_injected_bulk_query_is_denied():
    harness = DemoHarness(scenario="insurance", live=False)
    results = await harness.run()
    query = next(r for r in results if r["tool_name"] == "db_query")
    assert query["decision"] == "deny"
    assert query["policy_name"] == "deny_unscoped_claims_query"


@pytest.mark.asyncio
async def test_the_injection_is_carried_by_a_document_the_agent_had_reason_to_read():
    """The trigger must be grounded: the agent reads the claim document as part
    of settlement, and the document is attacker-controlled."""
    harness = DemoHarness(scenario="insurance", live=False)
    results = await harness.run()
    tools = [r["tool_name"] for r in results]
    assert tools.index("read_claim_document") < tools.index("db_query")


@pytest.mark.asyncio
async def test_the_run_carries_a_real_workflow():
    harness = DemoHarness(scenario="insurance", live=False)
    results = await harness.run()
    assert all(r["workflow"] == "claims_settlement" for r in results)
    assert all(r["workflow"] != "unassigned" for r in results)


@pytest.mark.asyncio
async def test_two_runs_produce_identical_decisions():
    first = await DemoHarness(scenario="insurance", live=False).run()
    second = await DemoHarness(scenario="insurance", live=False).run()
    assert [r["decision"] for r in first] == [r["decision"] for r in second]


@pytest.mark.asyncio
async def test_the_held_payment_proceeds_once_a_named_human_approves(db_session):
    """The business beat is not the hold -- it is the hold plus the approval
    plus the approver's name on the record. Without this the demo shows a
    blocked payment, which is the security beat again."""
    from sqlalchemy import select
    from app.models.schemas import HITLReview

    harness = DemoHarness(scenario="insurance", live=False)
    results = await harness.run()
    payment = next(r for r in results if r["tool_name"] == "release_payment")

    review = (await db_session.execute(
        select(HITLReview).where(HITLReview.audit_event_id == payment["audit_event_id"])
    )).scalar_one()
    assert review.status == "pending"

    approved = await harness.approve(review_id=review.id, approver="dana.okafor")
    assert approved["decision"] == "allow"

    await db_session.refresh(review)
    assert review.status == "approved"
    assert review.reviewer == "dana.okafor"


@pytest.mark.asyncio
async def test_the_approval_beat_is_absent_on_a_free_install(monkeypatch):
    """HITL is paid (spec §7). On a free core the same run produces the deny
    beat and reports the review beat as unavailable rather than silently
    skipping it."""
    from app.core import license_gate
    monkeypatch.setattr(license_gate, "has_enterprise_license", lambda: False)

    harness = DemoHarness(scenario="insurance", live=False)
    results = await harness.run()
    query = next(r for r in results if r["tool_name"] == "db_query")
    assert query["decision"] == "deny"
    assert harness.skipped_beats == ["human_approval:requires_enterprise_license"]
