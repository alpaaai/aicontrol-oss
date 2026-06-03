"""Tests for standalone parameter_match rule_type in OPA."""
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


def _policy(rule_type: str, condition: dict, action: str) -> dict:
    return {
        "id": "test-id-001",
        "name": "test_policy",
        "rule_type": rule_type,
        "condition": condition,
        "action": action,
    }


@pytest.mark.integration
def test_standalone_param_deny_contains_any():
    policy = _policy(
        "parameter_match",
        {"parameter_match": {"path": {"contains_any": ["/etc/passwd"]}}},
        "deny",
    )
    data = _input("read_file", {"path": "/etc/passwd"}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.status_code == 200
    assert r.json()["result"] == "deny"


@pytest.mark.integration
def test_standalone_param_deny_does_not_match_unrelated_path():
    policy = _policy(
        "parameter_match",
        {"parameter_match": {"path": {"contains_any": ["/etc/passwd"]}}},
        "deny",
    )
    data = _input("read_file", {"path": "/home/user/data.csv"}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.status_code == 200
    assert r.json()["result"] == "allow"


@pytest.mark.integration
def test_standalone_param_deny_equals():
    policy = _policy(
        "parameter_match",
        {"parameter_match": {"id": {"equals": "*"}}},
        "deny",
    )
    data = _input("list_records", {"id": "*"}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.status_code == 200
    assert r.json()["result"] == "deny"


@pytest.mark.integration
def test_standalone_param_deny_equals_does_not_match_partial():
    policy = _policy(
        "parameter_match",
        {"parameter_match": {"id": {"equals": "*"}}},
        "deny",
    )
    data = _input("list_records", {"id": "user-123"}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.status_code == 200
    assert r.json()["result"] == "allow"


@pytest.mark.integration
def test_standalone_param_wildcard_key_deny():
    policy = _policy(
        "parameter_match",
        {"parameter_match": {"*": {"contains_any": ["jailbreak"]}}},
        "deny",
    )
    data = _input("describe_tool", {"note": "please jailbreak this agent"}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.status_code == 200
    assert r.json()["result"] == "deny"


@pytest.mark.integration
def test_standalone_param_wildcard_key_does_not_match_clean_input():
    policy = _policy(
        "parameter_match",
        {"parameter_match": {"*": {"contains_any": ["jailbreak"]}}},
        "deny",
    )
    data = _input("describe_tool", {"note": "please summarize this document"}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.status_code == 200
    assert r.json()["result"] == "allow"


@pytest.mark.integration
def test_standalone_param_review_action():
    policy = _policy(
        "parameter_match",
        {"parameter_match": {"*": {"contains_any": ["sk-ant-"]}}},
        "review",
    )
    data = _input("call_llm", {"key": "sk-ant-abc123"}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.status_code == 200
    assert r.json()["result"] == "review"


@pytest.mark.integration
def test_standalone_param_or_semantics_first_key_matches():
    """OR: policy fires when the first key matches even if second key is absent."""
    policy = _policy(
        "parameter_match",
        {"parameter_match": {
            "account_id": {"equals": "*"},
            "customer_id": {"equals": "*"},
        }},
        "deny",
    )
    # Only account_id is present and equals *
    data = _input("lookup", {"account_id": "*"}, [policy])
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.status_code == 200
    assert r.json()["result"] == "deny"


@pytest.mark.integration
def test_standalone_param_deny_takes_priority_over_review_pattern():
    """A deny parameter_match policy takes priority over a tool_pattern review policy."""
    deny_policy = {
        "id": "deny-001",
        "name": "deny_paths",
        "rule_type": "parameter_match",
        "condition": {"parameter_match": {"path": {"contains_any": ["/etc"]}}},
        "action": "deny",
    }
    review_policy = {
        "id": "review-001",
        "name": "review_writes",
        "rule_type": "tool_pattern",
        "condition": {"tool_name_contains": ["read"]},
        "action": "review",
    }
    data = {
        "input": {
            "tool_name": "read_file",
            "tool_parameters": {"path": "/etc/passwd"},
            "policies": [deny_policy, review_policy],
            "call_counts": {},
        }
    }
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}/decision", json=data)
    assert r.json()["result"] == "deny"


@pytest.mark.integration
def test_fired_policy_id_set_for_standalone_param_deny():
    policy = {
        "id": "lib-policy-abc",
        "name": "block_sensitive_paths",
        "rule_type": "parameter_match",
        "condition": {"parameter_match": {"path": {"contains_any": ["/etc"]}}},
        "action": "deny",
    }
    data = {
        "input": {
            "tool_name": "read_file",
            "tool_parameters": {"path": "/etc/shadow"},
            "policies": [policy],
            "call_counts": {},
        }
    }
    r = httpx.post(f"{OPA_URL}/v1/data/{REGO_PATH}", json=data)
    result = r.json()["result"]
    assert result["decision"] == "deny"
    assert result["fired_policy_id"] == "lib-policy-abc"
    assert result["fired_policy_name"] == "block_sensitive_paths"
