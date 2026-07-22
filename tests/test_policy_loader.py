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
        assert "rule_type" in p
        assert "action" in p
        assert "condition" in p


def test_load_yaml_actions_are_valid():
    """All policy actions must be allow, deny, or review."""
    from app.services.policy_loader import load_yaml
    valid_actions = {"allow", "deny", "review"}
    for p in load_yaml():
        assert p["action"] in valid_actions, f"Invalid action: {p['action']}"


@pytest.mark.asyncio
async def test_upsert_policies_calls_db():
    """upsert_policies must execute one upsert per policy."""
    from app.services.policy_loader import upsert_policies

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    policies = [
        {"name": "test", "description": "", "rule_type": "default_allow",
         "condition": {}, "action": "allow", "severity": "low",
         "compliance_frameworks": []}
    ]
    await upsert_policies(mock_session, policies)
    assert mock_session.execute.called


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


def test_all_demo_seed_files_load_and_have_valid_actions():
    """Every YAML file under policies/demo_seeds/ must parse and contain only
    valid policy actions -- same contract as the default policies.yaml."""
    from app.services.policy_loader import load_yaml, DEMO_SEEDS_DIR
    valid_actions = {"allow", "deny", "review"}
    seed_files = sorted(DEMO_SEEDS_DIR.glob("*.yaml"))
    assert len(seed_files) == 6, f"expected 6 demo seed files, found {len(seed_files)}"
    for path in seed_files:
        for p in load_yaml(path):
            assert p["action"] in valid_actions, f"{path.name}: invalid action {p['action']}"
