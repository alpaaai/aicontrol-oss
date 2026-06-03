"""Tests for the seed_library_policies script."""
import pytest

EXPECTED_NAMES = [
    "block_shell_execution",
    "block_file_deletion",
    "block_cloud_metadata_access",
    "block_sensitive_file_reads",
    "block_wildcard_queries",
    "block_large_record_exports",
    "block_prompt_injection_in_params",
    "block_credential_patterns",
    "review_write_operations",
    "review_outbound_messaging",
    "review_high_value_transactions",
    "rate_limit_external_api_calls",
    "block_bulk_account_lookup",
    "review_wire_transfers",
    "deny_cross_patient_phi_access",
    "review_clinical_writes",
    "block_iam_modifications",
    "review_infrastructure_changes",
]


@pytest.mark.asyncio
async def test_all_library_policy_names_are_unique():
    """Names list has no duplicates — catches copy-paste errors in the script."""
    assert len(EXPECTED_NAMES) == len(set(EXPECTED_NAMES))
    assert len(EXPECTED_NAMES) == 18


@pytest.mark.asyncio
async def test_library_policies_exist_after_seed():
    """After running the seed, all 18 names exist in the DB as library=true."""
    import importlib.util, sys, os

    spec = importlib.util.spec_from_file_location(
        "seed_library_policies",
        "/home/deven/aicontrol/scripts/seed_library_policies.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    await module.seed()

    from sqlalchemy import select
    from app.models.database import async_session_factory
    from app.models.schemas import Policy

    async with async_session_factory() as session:
        result = await session.execute(
            select(Policy).where(Policy.library == True)
        )
        policies = result.scalars().all()
        names = {p.name for p in policies}

    for expected in EXPECTED_NAMES:
        assert expected in names, f"Missing library policy: {expected}"
