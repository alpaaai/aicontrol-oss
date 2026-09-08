import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.services.governance_engine import evaluate_tool_call, GovernanceResult


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
