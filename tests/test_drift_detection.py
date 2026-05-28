"""Tests for P1-5: policy drift detection — pure detect_drift() function."""
import uuid

import pytest

from app.models.policy_warning import PolicyWarning


def test_policy_warning_model_importable():
    assert PolicyWarning.__tablename__ == "policy_warnings"


# ── Helpers ──────────────────────────────────────────────────────────────────

from app.services.drift_detector import AgentSnapshot, PolicySnapshot, detect_drift


def _agent(name, tools):
    return AgentSnapshot(id=uuid.uuid4(), name=name, approved_tools=tools)


def _policy(name, blocked, aliases=None):
    return PolicySnapshot(
        id=uuid.uuid4(), name=name,
        blocked_tools=blocked, tool_aliases=aliases or [],
    )


# ── UNGOVERNED_TOOL tests ─────────────────────────────────────────────────────

def test_ungoverned_tool_no_policies():
    """Agent has tools but zero policies exist — all tools are ungoverned."""
    agents = [_agent("agent-a", ["tool_x", "tool_y"])]
    warnings = detect_drift(agents, policies=[])
    ungoverned = [w for w in warnings if w.warning_type == "UNGOVERNED_TOOL"]
    assert {w.tool_name for w in ungoverned} == {"tool_x", "tool_y"}


def test_ungoverned_tool_partial_coverage():
    """Agent has two tools; policy covers only one — one UNGOVERNED_TOOL warning."""
    agents = [_agent("agent-a", ["tool_x", "tool_y"])]
    policies = [_policy("deny-x", ["tool_x"])]
    warnings = detect_drift(agents, policies)
    ungoverned = [w for w in warnings if w.warning_type == "UNGOVERNED_TOOL"]
    assert len(ungoverned) == 1
    assert ungoverned[0].tool_name == "tool_y"
    assert ungoverned[0].agent_name == "agent-a"


def test_ungoverned_tool_alias_counts_as_coverage():
    """Tool in agent's approved_tools matches a policy alias — NOT ungoverned."""
    agents = [_agent("agent-a", ["fetch_credit_data"])]
    policies = [_policy("deny-credit", ["query_credit_bureau"],
                        aliases=["fetch_credit_data"])]
    warnings = detect_drift(agents, policies)
    ungoverned = [w for w in warnings if w.warning_type == "UNGOVERNED_TOOL"]
    assert ungoverned == []


def test_ungoverned_tool_full_coverage_no_warnings():
    """All agent tools covered by policies — no UNGOVERNED_TOOL warnings."""
    agents = [_agent("agent-a", ["tool_x"])]
    policies = [_policy("deny-x", ["tool_x"])]
    warnings = detect_drift(agents, policies)
    ungoverned = [w for w in warnings if w.warning_type == "UNGOVERNED_TOOL"]
    assert ungoverned == []


def test_ungoverned_tool_empty_approved_tools_skipped():
    """Agent with empty approved_tools is skipped entirely."""
    agents = [_agent("unrestricted-agent", [])]
    warnings = detect_drift(agents, policies=[])
    assert warnings == []


# ── ORPHANED_POLICY tests ─────────────────────────────────────────────────────

def test_orphaned_policy_no_agents_with_tools():
    """Policy targets a tool but no agent with non-empty approved_tools declares it."""
    agents = [_agent("unrestricted", [])]   # empty — skipped
    policies = [_policy("deny-x", ["tool_x"])]
    warnings = detect_drift(agents, policies)
    orphaned = [w for w in warnings if w.warning_type == "ORPHANED_POLICY"]
    assert len(orphaned) == 1
    assert orphaned[0].tool_name == "tool_x"
    assert orphaned[0].policy_name == "deny-x"
    assert orphaned[0].agent_id is None


def test_orphaned_policy_agent_declares_tool_no_orphan():
    """At least one agent declares the tool — policy is not orphaned."""
    agents = [_agent("agent-a", ["tool_x"])]
    policies = [_policy("deny-x", ["tool_x"])]
    warnings = detect_drift(agents, policies)
    orphaned = [w for w in warnings if w.warning_type == "ORPHANED_POLICY"]
    assert orphaned == []


def test_orphaned_policy_aliases_not_checked():
    """
    Policy aliases are NOT checked for ORPHANED_POLICY.
    Agent declares the alias but not canonical blocked_tool — policy still orphaned.
    """
    agents = [_agent("agent-a", ["fetch_credit_data"])]   # alias only
    policies = [_policy("deny-credit", ["query_credit_bureau"],
                        aliases=["fetch_credit_data"])]
    warnings = detect_drift(agents, policies)
    orphaned = [w for w in warnings if w.warning_type == "ORPHANED_POLICY"]
    assert len(orphaned) == 1
    assert orphaned[0].tool_name == "query_credit_bureau"


def test_multiple_blocked_tools_per_policy_each_gets_warning():
    """Policy with 2 blocked tools, neither declared by any agent → 2 warnings."""
    agents = []
    policies = [_policy("deny-multi", ["tool_a", "tool_b"])]
    warnings = detect_drift(agents, policies)
    orphaned = [w for w in warnings if w.warning_type == "ORPHANED_POLICY"]
    assert {w.tool_name for w in orphaned} == {"tool_a", "tool_b"}


# ── Combined rename scenario ──────────────────────────────────────────────────

def test_rename_scenario_both_warning_types():
    """
    query_credit_bureau renamed to fetch_credit_data in agent.
    No alias updated. Expect UNGOVERNED_TOOL + ORPHANED_POLICY.
    """
    agents = [_agent("loan-underwriting-agent",
                     ["fetch_credit_data", "run_risk_model"])]
    policies = [
        _policy("deny_bulk_credit_query", ["query_credit_bureau"]),
        _policy("deny_risk_model_abuse", ["run_risk_model"]),
    ]
    warnings = detect_drift(agents, policies)
    ungoverned = [w for w in warnings if w.warning_type == "UNGOVERNED_TOOL"]
    orphaned = [w for w in warnings if w.warning_type == "ORPHANED_POLICY"]

    assert len(ungoverned) == 1
    assert ungoverned[0].tool_name == "fetch_credit_data"
    assert ungoverned[0].agent_name == "loan-underwriting-agent"

    assert len(orphaned) == 1
    assert orphaned[0].tool_name == "query_credit_bureau"
    assert orphaned[0].policy_name == "deny_bulk_credit_query"
