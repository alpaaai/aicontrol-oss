"""Tests for standalone numeric_conditions rule_type in OPA."""
import pytest
import httpx

OPA_URL = "http://localhost:8181"
REGO_PATH = "aicontrol"


def _input(tool_name: str, tool_params: dict, policies: list[dict]) -> dict:
    return {
        "input": {
            "tool_name": tool_name,
            "tool_parameters": tool_params,
            "policies": policies,
            "call_counts": {},
        }
    }


def _policy(condition: dict, action: str) -> dict:
    return {
        "id": "test-nc-001",
        "name": "test_numeric",
        "rule_type": "numeric_conditions",
        "condition": condition,
        "action": action,
    }


@pytest.mark.integration
def test_standalone_numeric_deny_gt():
    policy = _policy({"numeric_conditions": {"amount": {"op": ">", "value": 10000}}}, "deny")
    data = _input("transfer", {"amount": 15000}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.json()["result"] == "deny"


@pytest.mark.integration
def test_standalone_numeric_deny_gt_boundary_not_exceeded():
    policy = _policy({"numeric_conditions": {"amount": {"op": ">", "value": 10000}}}, "deny")
    data = _input("transfer", {"amount": 10000}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.json()["result"] == "allow"


@pytest.mark.integration
def test_standalone_numeric_deny_gte():
    policy = _policy({"numeric_conditions": {"limit": {"op": ">=", "value": 1000}}}, "deny")
    data = _input("export", {"limit": 1000}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.json()["result"] == "deny"


@pytest.mark.integration
def test_standalone_numeric_deny_lt():
    policy = _policy({"numeric_conditions": {"score": {"op": "<", "value": 0.5}}}, "deny")
    data = _input("check_score", {"score": 0.3}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.json()["result"] == "deny"


@pytest.mark.integration
def test_standalone_numeric_review_action():
    policy = _policy({"numeric_conditions": {"amount": {"op": ">", "value": 10000}}}, "review")
    data = _input("transfer", {"amount": 50000}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.json()["result"] == "review"


@pytest.mark.integration
def test_standalone_numeric_or_semantics_one_field_matches():
    """OR: first matching field fires the policy even if second field is absent."""
    policy = _policy(
        {"numeric_conditions": {
            "amount": {"op": ">", "value": 10000},
            "limit":  {"op": ">", "value": 1000},
        }},
        "deny",
    )
    data = _input("export", {"amount": 50000}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.json()["result"] == "deny"


@pytest.mark.integration
def test_fired_policy_id_set_for_standalone_numeric_deny():
    policy = {
        "id": "lib-nc-xyz",
        "name": "block_large_exports",
        "rule_type": "numeric_conditions",
        "condition": {"numeric_conditions": {"limit": {"op": ">", "value": 1000}}},
        "action": "deny",
    }
    data = {
        "input": {
            "tool_name": "export_records",
            "tool_parameters": {"limit": 5000},
            "policies": [policy],
            "call_counts": {},
        }
    }
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}", json=data)
    result = r.json()["result"]
    assert result["decision"] == "deny"
    assert result["fired_policy_id"] == "lib-nc-xyz"
