"""Tests for policy loader — YAML parsing and DB upsert logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


def test_load_yaml_returns_list_of_policies():
    """load_yaml must return a list of dicts with required keys."""
    from app.services.policy_loader import load_yaml
    policies = load_yaml()
    assert isinstance(policies, list)
    assert len(policies) > 0
    for p in policies:
        assert "name" in p
        assert "effect" in p
        assert "condition" in p
        assert "condition" in p


def test_load_yaml_effects_are_valid():
    """Every seed policy is a Cedar forbid, so its effect is deny or review.
    There is no "allow" effect -- that is the catch-all permit cedar_client
    appends to every bundle, not a policy row."""
    from app.services.policy_loader import load_yaml
    valid_effects = {"deny", "review"}
    for p in load_yaml():
        assert p["effect"] in valid_effects, f"Invalid effect: {p['effect']}"


@pytest.mark.asyncio
async def test_upsert_policies_compiles_cedar_text(db_session):
    """upsert_policies must compile each policy on the way in. A mock session
    cannot show that any more -- the loader now reads back an existing row to
    keep its id stable, and compiling is the behaviour worth asserting."""
    from cedarpy import PolicySet
    from sqlalchemy import select

    from app.models.schemas import Policy
    from app.services.policy_loader import upsert_policies

    await upsert_policies(db_session, [{
        "name": "test_loader_compiles",
        "description": "",
        "effect": "deny",
        "action_tool": "delete_database",
        "condition": {"numeric_conditions": {"rows": {"gt": 10}}},
        "severity": "low",
        "compliance_frameworks": [],
    }])

    row = (await db_session.execute(
        select(Policy).where(Policy.name == "test_loader_compiles")
    )).scalar_one()
    assert row.cedar_text, "loader stored no cedar_text"
    assert "context.rows > 10" in row.cedar_text
    PolicySet.from_str(row.cedar_text + "\npermit (principal, action, resource);")


def test_load_yaml_never_uses_compliance_tags_key():
    """Every policy in policies.yaml must use 'compliance_frameworks' (the key
    policy_loader.upsert_policies actually reads) -- not the unread
    'compliance_tags' key, which silently drops compliance metadata into an
    empty list on every API startup."""
    from app.services.policy_loader import load_yaml
    offenders = [p["name"] for p in load_yaml() if "compliance_tags" in p]
    assert offenders == [], f"policies still using unread 'compliance_tags' key: {offenders}"


def test_policies_yaml_excludes_demo_scenario_policies():
    """The default shipped seed (policies.yaml) must contain only generic
    policies -- demo-scenario-specific policies live under policies/demo_seeds/
    and are loaded explicitly by scripts/seed.py, never by app startup."""
    from app.services.policy_loader import load_yaml
    demo_only_names = {
        "deny_bulk_credit_query", "deny_bulk_credit_query_rate",
        "deny_cross_encounter_phi_access", "deny_bulk_account_lookup",
        "block_http_post_in_itsm", "deny_unscoped_crm_query",
        "review_high_value_claim_payment", "deny_unscoped_claims_query",
    }
    names = {p["name"] for p in load_yaml()}
    assert names.isdisjoint(demo_only_names), (
        f"demo-scenario policies leaked into default seed: {names & demo_only_names}"
    )


def test_load_yaml_accepts_explicit_path_for_demo_seeds():
    """load_yaml(path) must read an arbitrary policies-shaped YAML file, so
    demo seed files under policies/demo_seeds/ can reuse the same loader."""
    from app.services.policy_loader import load_yaml, DEMO_SEEDS_DIR
    policies = load_yaml(DEMO_SEEDS_DIR / "lending.yaml")
    names = {p["name"] for p in policies}
    assert names == {"deny_bulk_credit_query", "deny_bulk_credit_query_rate"}


def test_all_demo_seed_files_load_and_have_valid_effects():
    """Every YAML file under policies/demo_seeds/ must parse and contain only
    valid policy effects -- same contract as the default policies.yaml."""
    from app.services.policy_loader import load_yaml, DEMO_SEEDS_DIR
    valid_effects = {"deny", "review"}
    seed_files = sorted(DEMO_SEEDS_DIR.glob("*.yaml"))
    # 6 pre-phase-6 scenario files plus gtm.yaml (task 6.4 -- GTM sales
    # outreach, the demo-harness successor to the revops.yaml scenario).
    assert len(seed_files) == 7, f"expected 7 demo seed files, found {len(seed_files)}"
    for path in seed_files:
        for p in load_yaml(path):
            assert p["effect"] in valid_effects, f"{path.name}: invalid effect {p['effect']}"
