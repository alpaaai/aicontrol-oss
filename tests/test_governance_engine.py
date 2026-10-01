import uuid
from datetime import datetime, timedelta

import pytest
from unittest.mock import AsyncMock, patch

from app.core.license_gate import LicenseInfo
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

    # get_scoped_policies is mocked (as in the sibling test above) so this
    # unit test exercises evaluate_tool_call's own decision logic in
    # isolation -- an unmocked real query would also pick up the shipped
    # default block_unapproved_outbound_http policy, which matches
    # http_post just as unscoped as this test's own policy and could win
    # the "which policy fired" attribution depending on row order. Real
    # seeded-policy behavior is covered separately by
    # tests/test_demo_scenario_decisions.py.
    scoped_policy = {
        "id": str(policy_id), "name": policy.name, "cedar_text": policy.cedar_text,
        "effect": "deny", "condition": {}, "action_tool": "http_post", "severity": None,
    }
    with patch("app.services.governance_engine.get_scoped_policies", new=AsyncMock(return_value=[scoped_policy])):
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


@pytest.mark.asyncio
async def test_evaluate_and_enforce_collapses_review_to_deny_on_community_license(db_session):
    """Community has no Slack notification and no /reviews API access -- a
    review decision must never reach the HITL-creation branch for a
    community-licensed deployment, or it blocks forever with no path to
    resolution."""
    from app.models.schemas import Agent

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-7", owner="qa", approved_tools=[], governance_mode="govern")
    db_session.add(agent)
    await db_session.flush()

    review_result = GovernanceResult(
        decision="review", reason="require_review_for_external_calls",
        fired_policy_id=None, fired_policy_name=None, bypass=False, system="http",
    )
    community_info = LicenseInfo(plan="community", company=None, email=None, expires_at=None)

    with patch("app.services.governance_engine.evaluate_tool_call", new=AsyncMock(return_value=review_result)), \
         patch("app.services.governance_engine.maybe_alert_budget_threshold", new=AsyncMock()), \
         patch("app.services.governance_engine.get_license_info", return_value=community_info):
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

    assert result.decision == "deny"
    assert result.reason == "review_requires_business_license: require_review_for_external_calls"
    assert result.enforced_decision == "deny"


@pytest.mark.asyncio
async def test_evaluate_and_enforce_leaves_review_alone_on_business_license(db_session):
    from app.models.schemas import Agent

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-8", owner="qa", approved_tools=[], governance_mode="govern")
    db_session.add(agent)
    await db_session.flush()

    review_result = GovernanceResult(
        decision="review", reason="require_review_for_external_calls",
        fired_policy_id=None, fired_policy_name=None, bypass=False, system="http",
    )
    business_info = LicenseInfo(plan="business", company=None, email=None, expires_at=None)

    with patch("app.services.governance_engine.evaluate_tool_call", new=AsyncMock(return_value=review_result)), \
         patch("app.services.governance_engine.maybe_alert_budget_threshold", new=AsyncMock()), \
         patch("app.services.governance_engine.get_license_info", return_value=business_info):
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

    assert result.decision == "review"
    assert result.reason == "require_review_for_external_calls"


@pytest.mark.asyncio
async def test_evaluate_and_enforce_collapses_review_to_deny_when_license_check_errors(db_session):
    """Fail-closed: if the license check itself raises, treat it as community
    rather than let a review decision through unresolved."""
    from app.models.schemas import Agent

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-9", owner="qa", approved_tools=[], governance_mode="govern")
    db_session.add(agent)
    await db_session.flush()

    review_result = GovernanceResult(
        decision="review", reason="require_review_for_external_calls",
        fired_policy_id=None, fired_policy_name=None, bypass=False, system="http",
    )

    with patch("app.services.governance_engine.evaluate_tool_call", new=AsyncMock(return_value=review_result)), \
         patch("app.services.governance_engine.maybe_alert_budget_threshold", new=AsyncMock()), \
         patch("app.services.governance_engine.get_license_info", side_effect=RuntimeError("boom")):
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

    assert result.decision == "deny"
    assert result.reason == "review_requires_business_license: require_review_for_external_calls"


async def _make_review_policy(db_session, *, name: str, tool_name: str):
    from app.models.schemas import Policy
    from app.services.policy_compiler import compile_policy

    policy = Policy(
        id=uuid.uuid4(), name=name, condition={}, principal_type=None,
        principal_id=None, action_tool=tool_name, resource_system=None, effect="review",
    )
    policy.cedar_text = compile_policy(policy)
    db_session.add(policy)
    await db_session.flush()
    return {
        "id": str(policy.id), "name": policy.name, "cedar_text": policy.cedar_text,
        "effect": "review", "condition": {}, "action_tool": tool_name, "severity": None,
    }


async def _make_approved_review(db_session, *, agent_id, session_id, tool_name, tool_parameters, reviewed_at):
    from app.models.schemas import AuditEvent, HITLReview, Session

    db_session.add(Session(id=session_id, agent_id=agent_id))
    await db_session.flush()

    event = AuditEvent(
        id=uuid.uuid4(), session_id=session_id, sequence_number=1,
        tool_name=tool_name, tool_parameters=tool_parameters,
        decision="review", decision_reason="test_review_policy",
    )
    db_session.add(event)
    await db_session.flush()

    review = HITLReview(
        id=uuid.uuid4(), audit_event_id=event.id, session_id=session_id,
        status="approved", reviewed_at=reviewed_at,
    )
    db_session.add(review)
    await db_session.flush()
    return event, review


@pytest.mark.asyncio
async def test_evaluate_tool_call_allows_retry_of_approved_review(db_session):
    """An identical call retried in the same session after HITL approval must
    pass, not be re-flagged for review -- otherwise approval never actually
    unblocks the caller (Task 4)."""
    from app.models.schemas import Agent

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-10", owner="qa", approved_tools=[])
    db_session.add(agent)
    await db_session.flush()

    session_id = uuid.uuid4()
    # audit_events.tool_parameters stores the mcp_gateway-enriched dict
    # (raw + a "domain" key for http_* tools); the retry match must use
    # containment against that stored value, not exact equality, since
    # evaluate_tool_call itself only ever sees raw tool_parameters.
    tool_parameters = {"url": "https://example.com", "domain": "example.com"}
    await _make_approved_review(
        db_session, agent_id=agent.id, session_id=session_id, tool_name="http_get",
        tool_parameters=tool_parameters, reviewed_at=datetime.utcnow() - timedelta(minutes=5),
    )

    scoped_policy = await _make_review_policy(db_session, name="test_review_http_get", tool_name="http_get")

    with patch("app.services.governance_engine.get_scoped_policies", new=AsyncMock(return_value=[scoped_policy])):
        result = await evaluate_tool_call(
            db_session,
            agent=agent,
            agent_name=agent.name,
            tool_name="http_get",
            tool_parameters={"url": "https://example.com"},
            workflow="unassigned",
            session_id=session_id,
        )

    assert result.decision == "allow"
    assert result.reason == "hitl_approved_retry"


@pytest.mark.asyncio
async def test_evaluate_tool_call_does_not_retry_outside_window(db_session):
    """An approval older than HITL_RETRY_WINDOW_MINUTES must not override a
    fresh review decision -- the retry window is not indefinite."""
    from app.models.schemas import Agent
    from app.core.config import settings

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-11", owner="qa", approved_tools=[])
    db_session.add(agent)
    await db_session.flush()

    session_id = uuid.uuid4()
    tool_parameters = {"url": "https://example.com", "domain": "example.com"}
    await _make_approved_review(
        db_session, agent_id=agent.id, session_id=session_id, tool_name="http_get",
        tool_parameters=tool_parameters,
        reviewed_at=datetime.utcnow() - timedelta(minutes=settings.HITL_RETRY_WINDOW_MINUTES + 5),
    )

    scoped_policy = await _make_review_policy(db_session, name="test_review_http_get_2", tool_name="http_get")

    with patch("app.services.governance_engine.get_scoped_policies", new=AsyncMock(return_value=[scoped_policy])):
        result = await evaluate_tool_call(
            db_session,
            agent=agent,
            agent_name=agent.name,
            tool_name="http_get",
            tool_parameters={"url": "https://example.com"},
            workflow="unassigned",
            session_id=session_id,
        )

    assert result.decision == "review"


@pytest.mark.asyncio
async def test_evaluate_tool_call_does_not_retry_different_session(db_session):
    """An approval from a different session must never authorize a retry --
    the match is scoped per-session, not global."""
    from app.models.schemas import Agent

    agent = Agent(id=uuid.uuid4(), name="test-agent-gov-12", owner="qa", approved_tools=[])
    db_session.add(agent)
    await db_session.flush()

    approved_session_id = uuid.uuid4()
    retry_session_id = uuid.uuid4()
    tool_parameters = {"url": "https://example.com", "domain": "example.com"}
    await _make_approved_review(
        db_session, agent_id=agent.id, session_id=approved_session_id, tool_name="http_get",
        tool_parameters=tool_parameters, reviewed_at=datetime.utcnow() - timedelta(minutes=5),
    )

    scoped_policy = await _make_review_policy(db_session, name="test_review_http_get_3", tool_name="http_get")

    with patch("app.services.governance_engine.get_scoped_policies", new=AsyncMock(return_value=[scoped_policy])):
        result = await evaluate_tool_call(
            db_session,
            agent=agent,
            agent_name=agent.name,
            tool_name="http_get",
            tool_parameters={"url": "https://example.com"},
            workflow="unassigned",
            session_id=retry_session_id,
        )

    assert result.decision == "review"
