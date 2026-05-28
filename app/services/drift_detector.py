"""Policy drift detection: pure function + background scheduler."""
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from app.core.logging import get_logger

logger = get_logger("drift_detector")


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class AgentSnapshot:
    id: uuid.UUID
    name: str
    approved_tools: list[str]


@dataclass
class PolicySnapshot:
    id: uuid.UUID
    name: str
    blocked_tools: list[str]
    tool_aliases: list[str] = field(default_factory=list)


@dataclass
class WarningRecord:
    warning_type: str           # UNGOVERNED_TOOL | ORPHANED_POLICY
    agent_id: uuid.UUID | None
    agent_name: str | None
    policy_id: uuid.UUID | None
    policy_name: str | None
    tool_name: str
    message: str


# ── Pure detection function ───────────────────────────────────────────────────

def detect_drift(
    agents: list[AgentSnapshot],
    policies: list[PolicySnapshot],
) -> list[WarningRecord]:
    """
    Pure function — no I/O.
    Returns UNGOVERNED_TOOL and ORPHANED_POLICY warnings.
    Agents with empty approved_tools are skipped entirely.
    """
    active_agents = [a for a in agents if a.approved_tools]

    # Build tool_name → list of covering policies (blocked_tools + aliases)
    policy_coverage: dict[str, list[PolicySnapshot]] = {}
    for policy in policies:
        for tool in policy.blocked_tools + policy.tool_aliases:
            policy_coverage.setdefault(tool, []).append(policy)

    # Set of all tools declared by agents with non-empty approved_tools
    declared_tools: set[str] = set()
    for agent in active_agents:
        declared_tools.update(agent.approved_tools)

    warnings: list[WarningRecord] = []

    # UNGOVERNED_TOOL: tool in agent's approved_tools but no policy covers it
    for agent in active_agents:
        for tool in agent.approved_tools:
            if tool not in policy_coverage:
                warnings.append(WarningRecord(
                    warning_type="UNGOVERNED_TOOL",
                    agent_id=agent.id,
                    agent_name=agent.name,
                    policy_id=None,
                    policy_name=None,
                    tool_name=tool,
                    message=(
                        f"Agent '{agent.name}' declares tool '{tool}' in approved_tools "
                        f"but no active policy references this tool name or its aliases. "
                        f"This tool is ungoverned — calls will pass through as default_allow."
                    ),
                ))

    # ORPHANED_POLICY: policy targets a tool no agent declares (blocked_tools only, not aliases)
    for policy in policies:
        for tool in policy.blocked_tools:
            if tool not in declared_tools:
                warnings.append(WarningRecord(
                    warning_type="ORPHANED_POLICY",
                    agent_id=None,
                    agent_name=None,
                    policy_id=policy.id,
                    policy_name=policy.name,
                    tool_name=tool,
                    message=(
                        f"Policy '{policy.name}' targets tool '{tool}' but no registered "
                        f"agent declares this tool in approved_tools. This policy may be "
                        f"orphaned due to a tool rename."
                    ),
                ))

    return warnings
