"""Tests for the token_budget OPA rule_type (WS3) — queries OPA directly,
mirroring the manual-curl verification pattern used to debug base.rego
during this session's bug-fix work."""
import httpx
import pytest

from app.core.config import settings


@pytest.fixture
async def push_current_rego():
    """Push this worktree's base.rego to the running OPA instance before each test."""
    from app.services.policy_loader import push_rego_to_opa
    await push_rego_to_opa()


@pytest.mark.asyncio
async def test_token_budget_hard_limit_denies(push_current_rego):
    payload = {
        "input": {
            "tool_name": "expensive_llm_call",
            "tool_parameters": {},
            "policies": [{
                "id": "p1", "name": "test_token_budget", "rule_type": "tool_denylist",
                "condition": {
                    "blocked_tools": ["expensive_llm_call"],
                    "token_budget": {"max_tokens": 100000, "window": "session", "on_exceed": "deny"},
                },
                "action": "deny", "severity": "high",
            }],
            "current_time": {"day_of_week": 2, "hour": 12},
            "call_counts": {},
            "cumulative_tokens": {"expensive_llm_call": 150000},
            "cumulative_cost_usd": {},
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{settings.opa_url}/v1/data/aicontrol", json=payload)
    result = resp.json()["result"]
    assert result["decision"] == "deny"
    assert "token_budget_exceeded" in result["reason"]


@pytest.mark.asyncio
async def test_token_budget_under_limit_allows(push_current_rego):
    payload = {
        "input": {
            "tool_name": "expensive_llm_call",
            "tool_parameters": {},
            "policies": [{
                "id": "p1", "name": "test_token_budget_2", "rule_type": "tool_denylist",
                "condition": {
                    "blocked_tools": ["expensive_llm_call"],
                    "token_budget": {"max_tokens": 100000, "window": "session", "on_exceed": "deny"},
                },
                "action": "deny", "severity": "high",
            }],
            "current_time": {"day_of_week": 2, "hour": 12},
            "call_counts": {},
            "cumulative_tokens": {"expensive_llm_call": 50000},
            "cumulative_cost_usd": {},
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{settings.opa_url}/v1/data/aicontrol", json=payload)
    assert resp.json()["result"]["decision"] == "allow"


@pytest.mark.asyncio
async def test_cost_budget_soft_limit_reviews(push_current_rego):
    payload = {
        "input": {
            "tool_name": "expensive_llm_call",
            "tool_parameters": {},
            "policies": [{
                "id": "p1", "name": "test_cost_budget", "rule_type": "tool_denylist",
                "condition": {
                    "blocked_tools": ["expensive_llm_call"],
                    "token_budget": {"max_cost_usd": 5.0, "window": "session", "on_exceed": "review"},
                },
                "action": "deny", "severity": "high",
            }],
            "current_time": {"day_of_week": 2, "hour": 12},
            "call_counts": {},
            "cumulative_tokens": {},
            "cumulative_cost_usd": {"expensive_llm_call": 7.50},
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{settings.opa_url}/v1/data/aicontrol", json=payload)
    assert resp.json()["result"]["decision"] == "review"
