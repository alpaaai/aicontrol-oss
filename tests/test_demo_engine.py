"""Tests for scripts/demos/engine.py — the shared rendering/execution engine
behind every demo scenario. Pure-logic helpers are tested directly; the
network-calling run functions are tested with a mocked httpx.AsyncClient
(see test_run_intercept_* below) so no live stack is required."""
from scripts.demos import engine


def test_decision_style_known_decisions():
    assert engine.decision_style("allow") == ("green", "✓")
    assert engine.decision_style("deny") == ("red", "✗")
    assert engine.decision_style("review") == ("yellow", "⚑")


def test_decision_style_unknown_decision_falls_back():
    assert engine.decision_style("error") == ("white", "?")


def test_v2_badge_present():
    call = {"v2_feature": "rate_limit"}
    assert engine.v2_badge(call) == "  [bold magenta][V2: RATE_LIMIT][/bold magenta]"


def test_v2_badge_absent():
    assert engine.v2_badge({}) == ""


def test_select_deny_detail_defaults_to_reason():
    scenario = {}
    data = {"reason": "tool_not_approved_for_agent", "policy_name": "approved_tools"}
    assert engine.select_deny_detail(scenario, data) == "tool_not_approved_for_agent"


def test_select_deny_detail_uses_configured_field():
    scenario = {"deny_detail_field": "policy_name"}
    data = {"reason": "tool_not_approved_for_agent", "policy_name": "approved_tools"}
    assert engine.select_deny_detail(scenario, data) == "approved_tools"


def test_select_deny_detail_returns_none_when_field_missing():
    scenario = {"deny_detail_field": "policy_name"}
    data = {"reason": "tool_not_approved_for_agent", "policy_name": None}
    assert engine.select_deny_detail(scenario, data) is None


def test_build_intercept_payload():
    scenario = {"agent_id": "00000000-0000-0000-0000-000000000010", "agent_name": "loan-underwriting-agent"}
    call = {"tool_name": "query_credit_bureau", "tool_parameters": {"applicant_id": "APP-1"}}
    payload = engine.build_intercept_payload(scenario, "session-123", call, 2)
    assert payload == {
        "session_id": "session-123",
        "agent_id": "00000000-0000-0000-0000-000000000010",
        "agent_name": "loan-underwriting-agent",
        "tool_name": "query_credit_bureau",
        "tool_parameters": {"applicant_id": "APP-1"},
        "sequence_number": 2,
    }


from unittest.mock import AsyncMock, MagicMock, patch


def _mock_async_client(*json_returns):
    """Build a mock httpx.AsyncClient usable as `async with httpx.AsyncClient() as client`.
    Each call to client.post() returns the next entry in json_returns (repeats the
    last one if there are more posts than entries)."""
    responses = []
    for payload in json_returns:
        resp = MagicMock()
        resp.json.return_value = payload
        responses.append(resp)

    client = MagicMock()
    client.post = AsyncMock(side_effect=responses)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


async def test_run_intercept_posts_expected_payload(capsys):
    scenario = {
        "kind": "intercept",
        "name": "Test Scenario",
        "agent_id": "00000000-0000-0000-0000-000000000099",
        "agent_name": "test-agent",
        "description": "test description",
        "tool_calls": [
            {"tool_name": "test_tool", "tool_parameters": {"key": "value"}, "label": "Test call", "expected": "allow"},
        ],
    }
    client = _mock_async_client({"decision": "allow", "reason": "default_allow"})
    with patch("scripts.demos.engine.httpx.AsyncClient", return_value=client):
        await engine._run_intercept(scenario, token="test-token", mode="fast")

    client.post.assert_awaited_once()
    _, kwargs = client.post.call_args
    assert kwargs["json"] == {
        "session_id": kwargs["json"]["session_id"],  # generated per-run, just check shape
        "agent_id": "00000000-0000-0000-0000-000000000099",
        "agent_name": "test-agent",
        "tool_name": "test_tool",
        "tool_parameters": {"key": "value"},
        "sequence_number": 1,
    }
    assert kwargs["headers"] == {"Authorization": "Bearer test-token"}

    out = capsys.readouterr().out
    assert "DECISION: ALLOW" in out
    assert "Session Summary" in out


async def test_run_intercept_shows_v2_badge_and_deny_detail(capsys):
    scenario = {
        "kind": "intercept",
        "name": "Test Scenario",
        "agent_id": "00000000-0000-0000-0000-000000000099",
        "agent_name": "test-agent",
        "description": "test description",
        "tool_calls": [
            {
                "tool_name": "rate_limited_tool", "tool_parameters": {}, "label": "Rate limited call",
                "expected": "deny", "v2_feature": "rate_limit",
            },
        ],
    }
    client = _mock_async_client({"decision": "deny", "reason": "rate_limit_exceeded:test:2:session"})
    with patch("scripts.demos.engine.httpx.AsyncClient", return_value=client):
        await engine._run_intercept(scenario, token="test-token", mode="fast")

    out = capsys.readouterr().out
    assert "[V2: RATE_LIMIT]" in out
    assert "Policy: rate_limit_exceeded:test:2:session" in out


async def test_run_intercept_shows_review_note_only_when_configured(capsys):
    scenario = {
        "kind": "intercept",
        "name": "Test Scenario",
        "agent_id": "00000000-0000-0000-0000-000000000099",
        "agent_name": "test-agent",
        "description": "test description",
        "deny_detail_field": "policy_name",
        "tool_calls": [
            {
                "tool_name": "payment_tool", "tool_parameters": {}, "label": "Payment call",
                "expected": "review", "review_note": "Routed to senior adjuster via Slack for approval",
            },
        ],
    }
    client = _mock_async_client({"decision": "review", "reason": "requires_human_review", "policy_name": "review_high_value"})
    with patch("scripts.demos.engine.httpx.AsyncClient", return_value=client):
        await engine._run_intercept(scenario, token="test-token", mode="fast")

    out = capsys.readouterr().out
    assert "Routed to senior adjuster via Slack for approval" in out


import pytest
import pytest_asyncio
from sqlalchemy import text
from app.models.database import async_session_factory


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _cleanup_test_mcp_servers():
    names = ["vendor-invoice-mcp", "claims-status-mcp"]
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM mcp_servers WHERE name = ANY(:names)"), {"names": names})
        await session.commit()
    yield
    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM mcp_servers WHERE name = ANY(:names)"), {"names": names})
        await session.commit()


def test_dispatch_routes_intercept_scenarios():
    with patch("scripts.demos.engine._run_intercept", new=AsyncMock()) as mock_run:
        engine.dispatch("insurance", token="tok", mode="fast")
        mock_run.assert_awaited_once()
        args, _ = mock_run.call_args
        assert args[0]["kind"] == "intercept"
        assert args[1] == "tok"
        assert args[2] == "fast"


def test_dispatch_defaults_mode_to_walkthrough():
    with patch("scripts.demos.engine._run_intercept", new=AsyncMock()) as mock_run:
        engine.dispatch("insurance", token="tok")
        args, _ = mock_run.call_args
        assert args[2] == "walkthrough"


def test_dispatch_unknown_scenario_raises_keyerror():
    import pytest
    with pytest.raises(KeyError):
        engine.dispatch("not_a_real_scenario", token="tok")
