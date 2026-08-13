"""Self-critique finding: policy_compliance_tags was never populated for
any real policy (policies/policies.yaml, policies/demo_seeds/) -- every
compliance report generated against real seeded data had an empty Control
Mapping section despite the aggregator/md_builder tests passing (they all
construct their own PolicyComplianceTag fixture rows). This seeds tags for
the named default + demo-scenario policies.

NIST AI RMF function names (GOVERN/MAP/MEASURE/MANAGE) and the EU AI Act
article numbers used here (9 = risk management system, 12 = record-keeping,
14 = human oversight) are the same anchors already used by this project's
own compliance test fixtures (tests/test_compliance_aggregator.py,
tests/test_compliance_router.py) -- not independently re-verified this
session. owasp_asi_tags are populated only for the two ASI codes already
established elsewhere in this codebase (ASI01 in
plans/v2/2026-08-12-..., ASI06 in memory_guard_adapter.py); no other ASI
code is asserted since this session did not verify the full OWASP Agentic
Security Initiative taxonomy against a primary source.
"""
import uuid

import pytest
from sqlalchemy import delete, select

from app.models.database import async_session_factory
from app.models.schemas import Policy


@pytest.mark.asyncio
async def test_seed_policy_compliance_tags_populates_known_policies():
    """block_dangerous_tools is one of the 4 real default-active policies
    loaded by app startup from policies/policies.yaml -- use the real row
    (it already exists in this shared dev DB) rather than inserting a
    duplicate, which would collide with policies.uq_policies_name."""
    from enterprise.compliance.models import PolicyComplianceTag
    from enterprise.compliance.policy_tag_seeds import POLICY_COMPLIANCE_TAGS, seed_policy_compliance_tags

    async with async_session_factory() as session:
        policy = (
            await session.execute(select(Policy).where(Policy.name == "block_dangerous_tools"))
        ).scalar_one_or_none()
        if policy is None:
            pytest.skip("block_dangerous_tools default policy not seeded in this DB")
        policy_id = policy.id

        pre_existing_tag = (
            await session.execute(select(PolicyComplianceTag).where(PolicyComplianceTag.policy_id == policy_id))
        ).scalar_one_or_none()

        try:
            await seed_policy_compliance_tags(session)
            await session.commit()

            tag = (
                await session.execute(
                    select(PolicyComplianceTag).where(PolicyComplianceTag.policy_id == policy_id)
                )
            ).scalar_one()
            expected = POLICY_COMPLIANCE_TAGS["block_dangerous_tools"]
            assert list(tag.nist_rmf_functions) == expected["nist_rmf_functions"]
            assert list(tag.eu_ai_act_articles) == expected["eu_ai_act_articles"]
            assert list(tag.owasp_asi_tags) == expected["owasp_asi_tags"]
        finally:
            if pre_existing_tag is None:
                await session.execute(delete(PolicyComplianceTag).where(PolicyComplianceTag.policy_id == policy_id))
                await session.commit()


@pytest.mark.asyncio
async def test_seed_policy_compliance_tags_skips_unknown_policy_names():
    """A policy name not present in POLICY_COMPLIANCE_TAGS is skipped, not
    an error -- this seeding function is best-effort against whatever
    subset of named policies happen to already exist in the DB."""
    from enterprise.compliance.policy_tag_seeds import seed_policy_compliance_tags

    async with async_session_factory() as session:
        await seed_policy_compliance_tags(session)  # must not raise
