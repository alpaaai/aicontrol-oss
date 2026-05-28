"""Tests for compliance report markdown builder."""
import uuid
from datetime import date

import pytest

from enterprise.compliance.aggregator import Layer3Context
from enterprise.compliance.md_builder import build_markdown


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
        {"policy_name": "deny_bulk_account_lookup", "decision": "deny", "count": 4},
    ],
    denied_sample=[
        {
            "timestamp": "2026-02-14T09:23:11Z",
            "agent": "loan-underwriting-agent",
            "tool": "execute_bulk_query",
            "policy": "deny_bulk_account_lookup",
            "parameters_summary": "query_type=bulk, record_count=450",
        }
    ],
    active_policy_count=11,
    hitl_review_count=0,
)

SAMPLE_NARRATIVES = {
    "eu_ai_act": "## EU AI Act\n\nArticle 12 — Record-keeping satisfied. 847 events logged.\n",
    "nist_ai_rmf": "## NIST AI RMF\n\nGOVERN 1.1 — 11 active policies established.\n",
}

REPORT_ID = uuid.uuid4()


def test_build_markdown_returns_string():
    result = build_markdown(SAMPLE_CONTEXT, SAMPLE_NARRATIVES, REPORT_ID, ["eu_ai_act", "nist_ai_rmf"])
    assert isinstance(result, str)
    assert len(result) > 500


def test_all_section_headers_present():
    result = build_markdown(SAMPLE_CONTEXT, SAMPLE_NARRATIVES, REPORT_ID, ["eu_ai_act"])
    assert "## Executive Summary" in result
    assert "## Audit Scope" in result
    assert "## Agent Inventory" in result
    assert "## Policy Inventory" in result
    assert "## Interception Statistics" in result
    assert "## Denied Call Detail" in result
    assert "## Attestation of Technical Controls" in result


def test_report_id_in_header_and_attestation():
    report_id_str = str(REPORT_ID)
    result = build_markdown(SAMPLE_CONTEXT, SAMPLE_NARRATIVES, REPORT_ID, ["eu_ai_act"])
    assert report_id_str in result


def test_scope_limitation_text_present():
    result = build_markdown(SAMPLE_CONTEXT, SAMPLE_NARRATIVES, REPORT_ID, ["eu_ai_act"])
    assert "scope limitation" in result.lower() or "Scope limitation" in result


def test_narratives_included():
    result = build_markdown(SAMPLE_CONTEXT, SAMPLE_NARRATIVES, REPORT_ID, ["eu_ai_act", "nist_ai_rmf"])
    assert "Article 12" in result
    assert "GOVERN 1.1" in result


def test_agent_names_in_inventory():
    result = build_markdown(SAMPLE_CONTEXT, SAMPLE_NARRATIVES, REPORT_ID, ["eu_ai_act"])
    assert "loan-underwriting-agent" in result
    assert "customer-support-agent" in result


def test_policy_names_in_inventory():
    result = build_markdown(SAMPLE_CONTEXT, SAMPLE_NARRATIVES, REPORT_ID, ["eu_ai_act"])
    assert "block_dangerous_tools" in result
    assert "deny_bulk_account_lookup" in result


def test_statistics_in_document():
    result = build_markdown(SAMPLE_CONTEXT, SAMPLE_NARRATIVES, REPORT_ID, ["eu_ai_act"])
    assert "847" in result
    assert "1.4" in result
