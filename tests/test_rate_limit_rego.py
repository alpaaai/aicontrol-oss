"""Tests for P1-2 rate-limit Rego rules via OPA CLI subprocess evaluation."""
import json
import subprocess
from pathlib import Path

import pytest

REGO_PATH = Path("policies/base.rego")
OPA_CONTAINER = "aicontrol-opa-1"

RATE_LIMIT_POLICY = {
    "id": "pol-rate-001",
    "name": "deny_bulk_credit_query_rate",
    "rule_type": "rate_limit",
    "action": "deny",
    "condition": {
        "tools": ["query_credit_bureau"],
        "rate_limit": {
            "max_calls": 10,
            "window": "session",
        },
    },
}

RATE_LIMIT_REVIEW_POLICY = {
    "id": "pol-rate-002",
    "name": "review_high_frequency_payments",
    "rule_type": "rate_limit",
    "action": "review",
    "condition": {
        "tools": ["approve_claim_payment"],
        "rate_limit": {
            "max_calls": 3,
            "window": "5m",
            "on_exceed": "review",
        },
    },
}


def evaluate_rego(input_data: dict) -> dict:
    """Evaluate base.rego with given input via OPA running in Docker."""
    rego_content = REGO_PATH.read_text()
    # Pass rego via stdin as a bundle-less eval: pipe rego then input as combined JSON
    # Use two-step: copy rego to container then eval with input via stdin
    combined = json.dumps({"rego": rego_content, "input": input_data})
    # Write rego to a temp file in the container via docker cp alternative:
    # Use opa eval with --stdin-input and inline data from echo
    input_json = json.dumps(input_data)
    rego_b64 = __import__("base64").b64encode(rego_content.encode()).decode()
    script = (
        f"echo {rego_b64} | base64 -d > /tmp/test_base.rego && "
        f"echo '{input_json}' | opa eval "
        f"--data /tmp/test_base.rego --stdin-input data.aicontrol"
    )
    result = subprocess.run(
        ["docker", "exec", "-i", OPA_CONTAINER, "sh", "-c", script],
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()
    return json.loads(result.stdout)["result"][0]["expressions"][0]["value"]


def make_input(tool_name: str, call_count: int, policies: list) -> dict:
    return {
        "tool_name": tool_name,
        "tool_parameters": {},
        "agent_id": "agent-001",
        "session_id": "sess-001",
        "timestamp": "2026-05-27T00:00:00Z",
        "call_counts": {tool_name: call_count} if call_count > 0 else {},
        "policies": policies,
    }


def test_rate_limit_deny_below_threshold():
    inp = make_input("query_credit_bureau", 9, [RATE_LIMIT_POLICY])
    result = evaluate_rego(inp)
    assert result["decision"] == "allow"


def test_rate_limit_deny_at_threshold():
    inp = make_input("query_credit_bureau", 10, [RATE_LIMIT_POLICY])
    result = evaluate_rego(inp)
    assert result["decision"] == "deny"
    assert result["reason"] == "rate_limit_exceeded:query_credit_bureau:10:session"


def test_rate_limit_deny_above_threshold():
    inp = make_input("query_credit_bureau", 15, [RATE_LIMIT_POLICY])
    result = evaluate_rego(inp)
    assert result["decision"] == "deny"


def test_rate_limit_review_on_exceed():
    inp = make_input("approve_claim_payment", 3, [RATE_LIMIT_REVIEW_POLICY])
    result = evaluate_rego(inp)
    assert result["decision"] == "review"
    assert result["reason"] == "rate_limit_exceeded:approve_claim_payment:3:5m"


def test_rate_limit_default_on_exceed_is_deny():
    policy_no_on_exceed = {
        **RATE_LIMIT_POLICY,
        "condition": {
            "tools": ["query_credit_bureau"],
            "rate_limit": {"max_calls": 10, "window": "session"},
        },
    }
    inp = make_input("query_credit_bureau", 10, [policy_no_on_exceed])
    result = evaluate_rego(inp)
    assert result["decision"] == "deny"


def test_rate_limit_does_not_fire_for_unrelated_tool():
    inp = make_input("delete_file", 99, [RATE_LIMIT_POLICY])
    result = evaluate_rego(inp)
    assert result["decision"] == "allow"


def test_rate_limit_priority_below_blacklist():
    blacklist_policy = {
        "id": "pol-bl-001",
        "name": "block_dangerous",
        "rule_type": "tool_denylist",
        "action": "deny",
        "condition": {"blocked_tools": ["query_credit_bureau"]},
    }
    inp = make_input("query_credit_bureau", 10, [RATE_LIMIT_POLICY, blacklist_policy])
    result = evaluate_rego(inp)
    assert result["decision"] == "deny"
    assert result["reason"] == "tool_denylisted"


def test_empty_call_counts_does_not_fire():
    inp = make_input("query_credit_bureau", 0, [RATE_LIMIT_POLICY])
    inp["call_counts"] = {}
    result = evaluate_rego(inp)
    assert result["decision"] == "allow"
