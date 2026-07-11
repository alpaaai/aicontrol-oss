"""Tests for token_budget condition validation on POST /policies (WS3)."""
import pytest


@pytest.mark.asyncio
async def test_token_budget_policy_requires_max_tokens_or_max_cost(client, admin_token):
    resp = await client.post("/policies", headers=admin_token, json={
        "name": "test_token_budget_missing_threshold",
        "description": "Invalid — no max_tokens or max_cost_usd",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["expensive_tool"],
            "token_budget": {"window": "session", "on_exceed": "deny"},
        },
        "action": "deny", "severity": "high", "active": True,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_token_budget_policy_requires_blocked_tools(client, admin_token):
    resp = await client.post("/policies", headers=admin_token, json={
        "name": "test_token_budget_missing_tools",
        "description": "Invalid — token_budget without blocked_tools",
        "rule_type": "tool_denylist",
        "condition": {
            "token_budget": {"max_tokens": 1000, "window": "session", "on_exceed": "deny"},
        },
        "action": "deny", "severity": "high", "active": True,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_valid_token_budget_policy_accepted(client, admin_token):
    resp = await client.post("/policies", headers=admin_token, json={
        "name": "test_token_budget_valid",
        "description": "Valid token_budget policy",
        "rule_type": "tool_denylist",
        "condition": {
            "blocked_tools": ["expensive_tool"],
            "token_budget": {"max_tokens": 100000, "window": "session", "on_exceed": "deny"},
        },
        "action": "deny", "severity": "high", "active": True,
    })
    assert resp.status_code == 201
