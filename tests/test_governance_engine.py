import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.services.governance_engine import evaluate_and_enforce, evaluate_tool_call, GovernanceResult


@pytest.mark.asyncio
async def test_evaluate_tool_call_returns_allow_with_no_matching_policy(db_session):
    from app.models.schemas import Agent

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-1", owner="qa", approved_tools=[])
    db_session.add(agent)
    await db_session.flush()

    with patch("app.services.governance_engine.get_scoped_policies", new=AsyncMock(return_value=[])):
        result = await evaluate_tool_call(
            db_session,
            agent=agent,
            agent_name=agent.name,
            tool_name="http_get",
            tool_parameters={"url": "https://example.com"},
            workflow="unassigned",
            session_id=uuid.uuid4(),
        )

    assert isinstance(result, GovernanceResult)
    assert result.decision == "allow"
    assert result.reason == "no_matching_policy"
    assert result.fired_policy_id is None


@pytest.mark.asyncio
async def test_evaluate_tool_call_denies_on_matching_policy(db_session):
    from app.models.schemas import Agent, Policy
    from app.services.policy_compiler import compile_policy

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-2", owner="qa", approved_tools=[])
    db_session.add(agent)

    policy_id = uuid.uuid4()
    policy = Policy(
        id=policy_id,
        name="test_deny_http_post",
        condition={},
        principal_type="agent",
        principal_id=None,
        action_tool="http_post",
        resource_system=None,
        effect="deny",
    )
    policy.cedar_text = compile_policy(policy)
    db_session.add(policy)
    await db_session.flush()

    result = await evaluate_tool_call(
        db_session,
        agent=agent,
        agent_name=agent.name,
        tool_name="http_post",
        tool_parameters={"url": "https://example.com"},
        workflow="unassigned",
        session_id=uuid.uuid4(),
    )

    assert result.decision == "deny"
    assert result.fired_policy_name == "test_deny_http_post"


@pytest.mark.asyncio
async def test_evaluate_and_enforce_gates_on_agent_level_approved_tools(db_session):
    """Reusable enforcement wrapper (plan 04 refactor task): an agent-level
    approved_tools allowlist must deny a non-approved tool before policy
    evaluation runs, same as app/routers/intercept.py's pre-gate."""
    from app.models.schemas import Agent

    agent = Agent(
        id=uuid.uuid4(), name="test-agent-gov-3", owner="qa",
        approved_tools=["http_get"], governance_mode="govern",
    )
    db_session.add(agent)
    await db_session.flush()

    result = await evaluate_and_enforce(
        db_session,
        agent=agent,
        agent_id=agent.id,
        agent_name=agent.name,
        tool_name="http_post",
        tool_parameters={},
        workflow="unassigned",
        session_id=uuid.uuid4(),
    )

    assert result.gated is True
    assert result.decision == "deny"
    assert result.reason == "tool_not_approved_for_agent"
    assert result.enforced_decision == "deny"


@pytest.mark.asyncio
async def test_evaluate_and_enforce_observe_mode_never_blocks(db_session):
    """observe-mode agents must have enforced_decision collapse to allow even
    when the true decision is deny, matching /intercept's is_observe_mode
    handling."""
    from app.models.schemas import Agent, Policy
    from app.services.policy_compiler import compile_policy

    agent = Agent(
        id=uuid.uuid4(), name="test-agent-gov-4", owner="qa",
        approved_tools=[], governance_mode="observe",
    )
    db_session.add(agent)

    policy = Policy(
        id=uuid.uuid4(), name="test_deny_http_post_observe", condition={},
        principal_type="agent", principal_id=None, action_tool="http_post",
        resource_system=None, effect="deny",
    )
    policy.cedar_text = compile_policy(policy)
    db_session.add(policy)
    await db_session.flush()

    result = await evaluate_and_enforce(
        db_session,
        agent=agent,
        agent_id=agent.id,
        agent_name=agent.name,
        tool_name="http_post",
        tool_parameters={"url": "https://example.com"},
        workflow="unassigned",
        session_id=uuid.uuid4(),
    )

    assert result.gated is False
    assert result.decision == "deny"
    assert result.is_observe_mode is True
    assert result.enforced_decision == "allow"


@pytest.mark.asyncio
async def test_evaluate_and_enforce_fires_budget_threshold_alert(db_session):
    """Budget-threshold alerting (app/services/budget_alert_service.py) must
    fire from the shared enforcement path so the MCP gateway gets it too,
    not only app/routers/intercept.py."""
    from app.models.schemas import Agent

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-5", owner="qa", approved_tools=[])
    db_session.add(agent)
    await db_session.flush()

    with patch("app.services.governance_engine.get_scoped_policies", new=AsyncMock(return_value=[])), \
         patch("app.services.governance_engine.maybe_alert_budget_threshold", new=AsyncMock()) as mock_alert:
        await evaluate_and_enforce(
            db_session,
            agent=agent,
            agent_id=agent.id,
            agent_name=agent.name,
            tool_name="http_get",
            tool_parameters={},
            workflow="unassigned",
            session_id=uuid.uuid4(),
        )
        import asyncio
        await asyncio.sleep(0)  # let the fire-and-forget create_task run

    mock_alert.assert_awaited_once()
    assert mock_alert.await_args.kwargs["tool_name"] == "http_get"


@pytest.mark.asyncio
async def test_evaluate_and_enforce_logs_critical_on_bypass(db_session):
    """A bypass decision from the Cedar engine must emit a critical log line
    from the shared enforcement path, matching /intercept's engine_bypass_event."""
    from app.models.schemas import Agent
    from app.services.governance_engine import GovernanceResult

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-6", owner="qa", approved_tools=[])
    db_session.add(agent)
    await db_session.flush()

    bypass_result = GovernanceResult(
        decision="allow", reason="engine_error_fail_open", fired_policy_id=None,
        fired_policy_name=None, bypass=True, system="unknown",
    )

    with patch("app.services.governance_engine.evaluate_tool_call", new=AsyncMock(return_value=bypass_result)), \
         patch("app.services.governance_engine.maybe_alert_budget_threshold", new=AsyncMock()), \
         patch("app.services.governance_engine.logger") as mock_logger:
        result = await evaluate_and_enforce(
            db_session,
            agent=agent,
            agent_id=agent.id,
            agent_name=agent.name,
            tool_name="http_get",
            tool_parameters={},
            workflow="unassigned",
            session_id=uuid.uuid4(),
        )

    assert result.bypass is True
    mock_logger.critical.assert_called_once()
    assert mock_logger.critical.call_args.args[0] == "engine_bypass_event"
