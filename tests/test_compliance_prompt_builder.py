"""Tests for compliance report prompt builder."""
import json
from datetime import date

import pytest

from enterprise.compliance.aggregator import Layer3Context
from enterprise.compliance.prompt_builder import build_prompt, ALLOWED_FRAMEWORKS


SAMPLE_CONTEXT = Layer3Context(
    date_from=date(2026, 1, 1),
    date_to=date(2026, 3, 31),
    total_intercepts=847,
    allowed=835,
    denied=12,
    reviewed=0,
    denial_rate_pct=1.4,
    agents=[
        {"name": "loan-underwriting-agent", "calls": 412, "denied": 8},
        {"name": "customer-support-agent", "calls": 312, "denied": 4},
    ],
    policies_fired=[
        {"policy_name": "block_dangerous_tools", "decision": "deny", "count": 8},
    ],
    denied_sample=[],
    active_policy_count=11,
    hitl_review_count=0,
)


def test_build_prompt_returns_three_layers():
    result = build_prompt(SAMPLE_CONTEXT, ["eu_ai_act"])
    assert "layer1" in result
    assert "layer2" in result
    assert "layer3" in result


def test_layer1_has_cache_control():
    result = build_prompt(SAMPLE_CONTEXT, ["eu_ai_act"])
    assert result["layer1_cache_control"] is True


def test_layer2_has_cache_control():
    result = build_prompt(SAMPLE_CONTEXT, ["eu_ai_act"])
    assert result["layer2_cache_control"] is True


def test_layer3_contains_actual_numbers():
    result = build_prompt(SAMPLE_CONTEXT, ["eu_ai_act", "nist_ai_rmf"])
    layer3 = result["layer3"]
    # Layer 3 must embed actual numbers from the context
    assert "847" in layer3        # total_intercepts
    assert "12" in layer3         # denied
    assert "1.4" in layer3        # denial_rate_pct
    assert "11" in layer3         # active_policy_count


def test_layer3_contains_requested_frameworks():
    result = build_prompt(SAMPLE_CONTEXT, ["eu_ai_act", "soc2"])
    layer3_data = json.loads(result["layer3"])
    assert "eu_ai_act" in layer3_data["frameworks_requested"]
    assert "soc2" in layer3_data["frameworks_requested"]


def test_layer3_is_valid_json():
    result = build_prompt(SAMPLE_CONTEXT, ["eu_ai_act"])
    layer3_data = json.loads(result["layer3"])
    assert "audit_summary" in layer3_data
    assert "agents" in layer3_data
    assert "policies_fired" in layer3_data


def test_allowed_frameworks_constant():
    assert "eu_ai_act" in ALLOWED_FRAMEWORKS
    assert "nist_ai_rmf" in ALLOWED_FRAMEWORKS
    assert "soc2" in ALLOWED_FRAMEWORKS
    assert "iso_42001" in ALLOWED_FRAMEWORKS


def test_layer2_contains_framework_mappings():
    result = build_prompt(SAMPLE_CONTEXT, ["eu_ai_act"])
    assert "Article 9" in result["layer2"] or "Article 12" in result["layer2"]
