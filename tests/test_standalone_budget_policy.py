"""Tests for the standalone rule_type == "budget" OPA rule (WS-F) --
aggregate agent-level/org-level budgets, independent of which tool is
called (unlike the existing tool_denylist.condition.token_budget, which
only fires for named blocked_tools). Mirrors tests/test_token_budget_policy.py's
direct-OPA testing convention exactly."""
import httpx
import pytest

from app.core.config import settings


@pytest.fixture
async def push_current_rego():
    from app.services.policy_loader import push_rego_to_opa
    await push_rego_to_opa()


@pytest.mark.asyncio
async def test_agent_level_budget_denies_when_exceeded(push_current_rego):
    payload = {
        "input": {
            "tool_name": "any_tool", "tool_parameters": {},
            "policies": [{
                "id": "p1", "name": "agent_monthly_cap", "rule_type": "budget",
                "condition": {"scope": "agent", "max_cost_usd": 100, "window": "session", "on_exceed": "deny"},
                "action": "deny", "severity": "high",
            }],
            "current_time": {"day_of_week": 2, "hour": 12},
            "call_counts": {}, "cumulative_tokens": {}, "cumulative_cost_usd": {},
            "agent_cumulative_cost_usd": 150,
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{settings.opa_url}/v1/data/aicontrol", json=payload)
    result = resp.json()["result"]
    assert result["decision"] == "deny"
    assert "budget_exceeded" in result["reason"]


@pytest.mark.asyncio
async def test_agent_level_budget_allows_under_threshold(push_current_rego):
    payload = {
        "input": {
            "tool_name": "any_tool", "tool_parameters": {},
            "policies": [{
                "id": "p1", "name": "agent_monthly_cap", "rule_type": "budget",
                "condition": {"scope": "agent", "max_cost_usd": 100, "window": "session", "on_exceed": "deny"},
                "action": "deny", "severity": "high",
            }],
            "current_time": {"day_of_week": 2, "hour": 12},
            "call_counts": {}, "cumulative_tokens": {}, "cumulative_cost_usd": {},
            "agent_cumulative_cost_usd": 50,
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{settings.opa_url}/v1/data/aicontrol", json=payload)
    assert resp.json()["result"]["decision"] == "allow"


@pytest.mark.asyncio
async def test_org_level_budget_review_on_exceed(push_current_rego):
    payload = {
        "input": {
            "tool_name": "any_tool", "tool_parameters": {},
            "policies": [{
                "id": "p1", "name": "org_monthly_cap", "rule_type": "budget",
                "condition": {"scope": "org", "max_tokens": 1000000, "window": "session", "on_exceed": "review"},
                "action": "review", "severity": "medium",
            }],
            "current_time": {"day_of_week": 2, "hour": 12},
            "call_counts": {}, "cumulative_tokens": {}, "cumulative_cost_usd": {},
            "org_cumulative_tokens": 1200000,
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{settings.opa_url}/v1/data/aicontrol", json=payload)
    assert resp.json()["result"]["decision"] == "review"
