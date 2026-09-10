"""Shared policy-evaluation pipeline. Called by both app/routers/intercept.py
(the SDK self-report path, being removed per plan 04) and the MCP gateway
(plan 02) so there is exactly one implementation of "how a tool call gets
evaluated" in the codebase, not two that can silently diverge.

Pulled out of app/routers/intercept.py unchanged in behavior — this task is
a pure extraction, not a rewrite. Audit writing (WAL vs. synchronous review
path) and HITL/Slack side effects stay in the caller for now (Task 2 moves
audit writing here too); this task only moves the read-only "what should
happen" decision.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.schemas import Agent, Policy
from app.services.budget_alert_service import maybe_alert_budget_threshold
from app.services.cedar_client import current_time_context, evaluate
from app.services.policy_compiler import ALL_PARAMS_FIELD
from app.services.rate_limit_service import build_call_counts
from app.services.system_resolver import UNKNOWN_SYSTEM, merge_unresolved, resolve_system
from app.services.token_budget_service import build_aggregate_budgets, build_token_budgets

logger = get_logger("governance_engine")


@dataclass
class GovernanceResult:
    decision: str
    reason: str
    fired_policy_id: Optional[str]
    fired_policy_name: Optional[str]
    bypass: bool
    system: str
    call_counts: dict = field(default_factory=dict)
    cumulative_tokens: dict = field(default_factory=dict)
    cumulative_cost_usd: dict = field(default_factory=dict)
    policies: list = field(default_factory=list)


async def get_scoped_policies(
    session: AsyncSession,
    *,
    agent_name: str,
    agent_groups: list[str],
    tool_name: str,
    system: str,
) -> list[dict]:
    """Load only the active policies whose scope matches this call.

    Moved verbatim from app/routers/intercept.py — see that module's git
    history for the original docstring explaining the scope-column design.
    """
    principal_match = or_(
        Policy.principal_id.is_(None),
        and_(Policy.principal_type == "agent", Policy.principal_id == agent_name),
        and_(Policy.principal_type == "group", Policy.principal_id.in_(agent_groups or [""])),
    )
    result = await session.execute(
        select(Policy).where(
            Policy.active == True,  # noqa: E712
            principal_match,
            or_(Policy.action_tool.is_(None), Policy.action_tool == tool_name),
            or_(Policy.resource_system.is_(None), Policy.resource_system == system),
        )
    )
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "effect": p.effect or "deny",
            "cedar_text": p.cedar_text,
            "condition": p.condition,
            "severity": p.severity,
            "action_tool": p.action_tool,
        }
        for p in result.scalars().all()
    ]


async def evaluate_tool_call(
    db: AsyncSession,
    *,
    agent: Optional[Agent],
    agent_name: str,
    tool_name: str,
    tool_parameters: dict[str, Any],
    workflow: str,
    session_id,
) -> GovernanceResult:
    """Run the full policy pipeline for one tool call and return the decision.
    Does not write any audit event or accumulate session risk — the caller
    (app/routers/intercept.py today, app's MCP gateway router in plan 02)
    owns persistence, since the two callers persist through different paths
    (WAL vs. gateway-specific audit fields)."""
    system = resolve_system(tool_name, tool_parameters)
    if system == UNKNOWN_SYSTEM and agent is not None:
        merged = merge_unresolved(agent.unresolved_systems, tool_name)
        if merged != (agent.unresolved_systems or []):
            agent.unresolved_systems = merged

    agent_groups: list[str] = list(getattr(agent, "groups", None) or []) if agent else []
    policies = await get_scoped_policies(
        db, agent_name=agent_name, agent_groups=agent_groups, tool_name=tool_name, system=system,
    )

    call_counts = await build_call_counts(
        db=db, agent_id=str(agent.id) if agent else None, session_id=str(session_id),
        tool_name=tool_name, active_policies=policies,
    )
    cumulative_tokens, cumulative_cost_usd = await build_token_budgets(
        db=db, agent_id=str(agent.id) if agent else None, session_id=str(session_id),
        tool_name=tool_name, active_policies=policies,
    )
    agent_cumulative, org_cumulative = await build_aggregate_budgets(
        db=db, agent_id=str(agent.id) if agent else None, active_policies=policies,
    )

    decision_result = await evaluate(
        agent_name=agent_name,
        agent_groups=agent_groups,
        tool_name=tool_name,
        system=system,
        context={
            "tool_name": tool_name,
            **tool_parameters,
            "workflow": workflow,
            ALL_PARAMS_FIELD: " ".join(str(v) for v in tool_parameters.values()),
            **current_time_context(),
            "call_count": call_counts.get(tool_name, 0),
            "cumulative_tokens": cumulative_tokens.get(tool_name, 0),
            "cumulative_cost_usd": cumulative_cost_usd.get(tool_name, 0),
            "agent_cumulative_tokens": agent_cumulative.get("tokens", 0),
            "agent_cumulative_cost_usd": agent_cumulative.get("cost_usd", 0),
            "org_cumulative_tokens": org_cumulative.get("tokens", 0),
            "org_cumulative_cost_usd": org_cumulative.get("cost_usd", 0),
        },
        policies=policies,
    )

    return GovernanceResult(
        decision=decision_result["decision"],
        reason=decision_result["reason"],
        fired_policy_id=decision_result.get("fired_policy_id") or None,
        fired_policy_name=decision_result.get("fired_policy_name") or None,
        bypass=decision_result.get("bypass", False),
        system=system,
        call_counts=call_counts,
        cumulative_tokens=cumulative_tokens,
        cumulative_cost_usd=cumulative_cost_usd,
        policies=policies,
    )


@dataclass
class EnforcementResult:
    """Result of evaluate_and_enforce: the true decision plus every side
    effect and mode-collapse rule that both app/routers/intercept.py and
    the MCP gateway need to apply identically (agent-level approved_tools
    gate, observe mode, budget-threshold alerting, bypass logging)."""
    decision: str
    reason: str
    enforced_decision: str
    is_observe_mode: bool
    fired_policy_id: Optional[str]
    fired_policy_name: Optional[str]
    bypass: bool
    gated: bool
    system: str = ""
    cumulative_tokens: dict = field(default_factory=dict)
    cumulative_cost_usd: dict = field(default_factory=dict)
    call_counts: dict = field(default_factory=dict)
    policies: list = field(default_factory=list)


async def evaluate_and_enforce(
    db: AsyncSession,
    *,
    agent: Optional[Agent],
    agent_id: uuid.UUID,
    agent_name: str,
    tool_name: str,
    tool_parameters: dict[str, Any],
    workflow: str,
    session_id,
) -> EnforcementResult:
    """Shared enforcement wrapper around evaluate_tool_call. Callers (both
    app/routers/intercept.py and app/routers/mcp_gateway.py) must apply
    `enforced_decision`, not `decision`, when deciding whether to actually
    block the call -- `decision` is what the policy engine determined,
    `enforced_decision` is what observe mode collapses it to."""
    is_observe_mode = agent is not None and agent.governance_mode == "observe"

    if agent is not None and agent.approved_tools and tool_name not in agent.approved_tools:
        return EnforcementResult(
            decision="deny",
            reason="tool_not_approved_for_agent",
            enforced_decision="allow" if is_observe_mode else "deny",
            is_observe_mode=is_observe_mode,
            fired_policy_id=None,
            fired_policy_name=None,
            bypass=False,
            gated=True,
        )

    gov_result = await evaluate_tool_call(
        db,
        agent=agent,
        agent_name=agent_name,
        tool_name=tool_name,
        tool_parameters=tool_parameters,
        workflow=workflow,
        session_id=session_id,
    )

    asyncio.create_task(maybe_alert_budget_threshold(
        cumulative_tokens=gov_result.cumulative_tokens,
        cumulative_cost_usd=gov_result.cumulative_cost_usd,
        active_policies=gov_result.policies,
        tool_name=tool_name,
    ))

    if gov_result.bypass:
        logger.critical(
            "engine_bypass_event",
            tool_name=tool_name,
            agent_id=str(agent_id),
            decision=gov_result.decision,
            reason=gov_result.reason,
        )

    return EnforcementResult(
        decision=gov_result.decision,
        reason=gov_result.reason,
        enforced_decision="allow" if is_observe_mode else gov_result.decision,
        is_observe_mode=is_observe_mode,
        fired_policy_id=gov_result.fired_policy_id,
        fired_policy_name=gov_result.fired_policy_name,
        bypass=gov_result.bypass,
        gated=False,
        system=gov_result.system,
        cumulative_tokens=gov_result.cumulative_tokens,
        cumulative_cost_usd=gov_result.cumulative_cost_usd,
        call_counts=gov_result.call_counts,
        policies=gov_result.policies,
    )
