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


async def test_cleanup_admission_scan_rows_deletes_prior_runs():
    scenario = {
        "kind": "admission_scan",
        "steps": [
            {"kind": "mcp_enroll", "name": "vendor-invoice-mcp", "base_url": "http://localhost:8901/mcp"},
            {"kind": "mcp_enroll", "name": "claims-status-mcp", "base_url": "http://localhost:8902/mcp"},
        ],
    }
    async with async_session_factory() as session:
        await session.execute(
            text("INSERT INTO mcp_servers (id, name, base_url) VALUES (gen_random_uuid(), :name, :base_url)"),
            {"name": "vendor-invoice-mcp", "base_url": "http://localhost:8901/mcp"},
        )
        await session.commit()

    await engine._cleanup_admission_scan_rows(scenario)

    async with async_session_factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM mcp_servers WHERE name = 'vendor-invoice-mcp'"))
        assert result.scalar_one() == 0


async def test_run_admission_scan_skill_scan_and_mcp_enroll(capsys):
    scenario = {
        "kind": "admission_scan",
        "name": "Test Admission Scan",
        "description": "test description",
        "steps": [
            {
                "kind": "skill_scan",
                "label": "Scan a skill",
                "narrative": "narrative text",
                "target_ref": "/fake/path",
                "insight": "insight text",
            },
            {
                "kind": "mcp_enroll",
                "label": "Enroll a server",
                "narrative": "narrative text",
                "name": "test-server",
                "base_url": "http://localhost:9999/mcp",
                "insight": "insight text",
            },
        ],
    }
    skill_scan_response = MagicMock()
    skill_scan_response.status_code = 201
    skill_scan_response.json.return_value = [{
        "severity_summary": {"critical": 1},
        "findings": [{"severity": "critical", "message": "bad thing", "rule_id": "R1", "location": None}],
    }]
    mcp_enroll_response = MagicMock()
    mcp_enroll_response.status_code = 201
    mcp_enroll_response.json.return_value = {"status": "blocked"}

    client = MagicMock()
    client.post = AsyncMock(side_effect=[skill_scan_response, mcp_enroll_response])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("scripts.demos.engine.httpx.AsyncClient", return_value=client):
        await engine._run_admission_scan(scenario, token="admin-token", mode="fast")

    out = capsys.readouterr().out
    assert "1 finding(s)" in out
    assert "STATUS: BLOCKED" in out
    assert "Session Summary" in out


async def test_run_mcp_gateway_setup_and_steps(capsys):
    scenario = {
        "kind": "mcp_gateway",
        "name": "Test Gateway",
        "description": "test description",
        "server_name": "test-tool-server",
        "downstream_base_url": "http://localhost:9998",
        "approved_tools": ["get_status"],
        "steps": [
            {
                "label": "List tools",
                "narrative": "narrative",
                "method": "tools/list",
                "body": {},
                "insight": "insight text",
            },
        ],
    }

    async with async_session_factory() as session:
        await session.execute(text("DELETE FROM mcp_servers WHERE name = :name"), {"name": "test-tool-server"})
        await session.commit()

    register_response = MagicMock()
    register_response.json.return_value = {"id": "11111111-1111-1111-1111-111111111111"}
    register_response.raise_for_status = MagicMock()
    tools_list_response = MagicMock()
    tools_list_response.json.return_value = {"tools": [{"name": "get_status"}]}

    client = MagicMock()
    client.post = AsyncMock(side_effect=[register_response, tools_list_response])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("scripts.demos.engine.httpx.AsyncClient", return_value=client):
        await engine._run_mcp_gateway(scenario, token="admin-token", mode="fast")

    out = capsys.readouterr().out
    assert "tools visible to agent" in out
    assert "Session Summary" in out

    async with async_session_factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM mcp_servers WHERE name = 'test-tool-server'"))
        assert result.scalar_one() == 1
        await session.execute(text("DELETE FROM mcp_servers WHERE name = 'test-tool-server'"))
        await session.commit()


def test_dispatch_routes_intercept_scenarios():
    with patch("scripts.demos.engine._run_intercept", new=AsyncMock()) as mock_run:
        engine.dispatch("lending", token="tok", mode="fast")
        mock_run.assert_awaited_once()
        args, _ = mock_run.call_args
        assert args[0]["kind"] == "intercept"
        assert args[1] == "tok"
        assert args[2] == "fast"


def test_dispatch_routes_admission_scan():
    with patch("scripts.demos.engine._run_admission_scan", new=AsyncMock()) as mock_run:
        engine.dispatch("admission_scanning", token="tok", mode="fast")
        mock_run.assert_awaited_once()
        args, _ = mock_run.call_args
        assert args[0]["kind"] == "admission_scan"


def test_dispatch_routes_mcp_gateway():
    with patch("scripts.demos.engine._run_mcp_gateway", new=AsyncMock()) as mock_run:
        engine.dispatch("mcp_gateway", token="tok", mode="fast")
        mock_run.assert_awaited_once()
        args, _ = mock_run.call_args
        assert args[0]["kind"] == "mcp_gateway"


def test_dispatch_defaults_mode_to_walkthrough():
    with patch("scripts.demos.engine._run_intercept", new=AsyncMock()) as mock_run:
        engine.dispatch("lending", token="tok")
        args, _ = mock_run.call_args
        assert args[2] == "walkthrough"


def test_dispatch_unknown_scenario_raises_keyerror():
    import pytest
    with pytest.raises(KeyError):
        engine.dispatch("not_a_real_scenario", token="tok")
