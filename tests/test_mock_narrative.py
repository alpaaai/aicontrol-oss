"""Mock-mode compliance narratives must reflect real aggregated data, never
hardcoded stats -- see AUDIT_AND_FIX_PLAN.md 4.1."""
from datetime import date

from enterprise.compliance.aggregator import Layer3Context
from enterprise.compliance.mock_narrative import build_mock_narrative
from enterprise.compliance.prompt_builder import ALLOWED_FRAMEWORKS


def _context(**overrides) -> Layer3Context:
    base = dict(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 3, 31),
        total_intercepts=200,
        allowed=180,
        denied=15,
        reviewed=5,
        denial_rate_pct=7.5,
        agents=[],
        policies_fired=[
            {"policy_name": "block_dangerous_tools", "decision": "deny", "count": 10},
            {"policy_name": "deny_bulk_account_lookup", "decision": "deny", "count": 5},
        ],
        denied_sample=[],
        reviewed_sample=[],
        active_policy_count=4,
        hitl_review_count=5,
        control_tags=[],
    )
    base.update(overrides)
    return Layer3Context(**base)


def test_returns_all_allowed_frameworks():
    result = build_mock_narrative(_context())
    assert set(result.keys()) == ALLOWED_FRAMEWORKS


def test_uses_real_totals_not_hardcoded_sample_numbers():
    ctx = _context(total_intercepts=200, denied=15, denial_rate_pct=7.5)
    result = build_mock_narrative(ctx)
    for framework, text in result.items():
        assert "847" not in text, f"{framework} still hardcodes the old fake total"
        assert "1.4" not in text, f"{framework} still hardcodes the old fake denial rate"
        assert "200" in text, f"{framework} does not surface the real total ({text[:200]})"


def test_reflects_a_different_dataset_differently():
    small = build_mock_narrative(_context(total_intercepts=3, denied=1, denial_rate_pct=33.3, active_policy_count=1, hitl_review_count=0))
    large = build_mock_narrative(_context(total_intercepts=90000, denied=9, denial_rate_pct=0.01, active_policy_count=20, hitl_review_count=50))
    assert small["eu_ai_act"] != large["eu_ai_act"]
    assert "3" in small["eu_ai_act"]
    assert "90,000" in large["eu_ai_act"] or "90000" in large["eu_ai_act"]


def test_names_top_denial_policy_when_present():
    ctx = _context(policies_fired=[
        {"policy_name": "block_dangerous_tools", "decision": "deny", "count": 8},
        {"policy_name": "deny_bulk_account_lookup", "decision": "deny", "count": 4},
    ])
    result = build_mock_narrative(ctx)
    assert "block_dangerous_tools" in result["nist_ai_rmf"]


def test_handles_zero_denials_without_naming_a_policy():
    ctx = _context(denied=0, denial_rate_pct=0.0, policies_fired=[])
    result = build_mock_narrative(ctx)
    for framework, text in result.items():
        assert "block_dangerous_tools" not in text
