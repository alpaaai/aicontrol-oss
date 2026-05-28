"""Policy drift detection: pure function + background scheduler."""
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, and_, Text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.policy_warning import PolicyWarning
from app.models.schemas import Agent, Policy

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


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _load_agents(session: AsyncSession) -> list[AgentSnapshot]:
    """Load agents with non-empty approved_tools."""
    result = await session.execute(
        select(Agent).where(Agent.approved_tools.cast(Text) != "[]")
    )
    return [
        AgentSnapshot(id=a.id, name=a.name, approved_tools=a.approved_tools or [])
        for a in result.scalars().all()
        if a.approved_tools  # double-guard
    ]


async def _load_policies(session: AsyncSession) -> list[PolicySnapshot]:
    """Load active tool_denylist policies and extract tool lists from condition JSONB."""
    result = await session.execute(
        select(Policy).where(
            and_(Policy.active == True, Policy.rule_type == "tool_denylist")
        )
    )
    snapshots = []
    for p in result.scalars().all():
        condition = p.condition or {}
        blocked = condition.get("blocked_tools", [])
        aliases = condition.get("tool_aliases", [])
        if blocked:
            snapshots.append(PolicySnapshot(
                id=p.id,
                name=p.name,
                blocked_tools=blocked,
                tool_aliases=aliases,
            ))
    return snapshots


async def _reconcile(session: AsyncSession, computed: list[WarningRecord]) -> None:
    """
    Reconcile computed warnings against DB state.
    New → insert. Gone (active) → auto-resolve. Resolved reappear → reactivate.
    """
    now = datetime.now(timezone.utc)

    result = await session.execute(select(PolicyWarning))
    db_warnings = result.scalars().all()

    def _dedup_key(w):
        return (w.warning_type, w.agent_id, w.policy_id, w.tool_name)

    db_index: dict = {_dedup_key(w): w for w in db_warnings}

    computed_keys: set = set()
    for rec in computed:
        key = (rec.warning_type, rec.agent_id, rec.policy_id, rec.tool_name)
        computed_keys.add(key)

        existing = db_index.get(key)
        if existing is None:
            session.add(PolicyWarning(
                warning_type=rec.warning_type,
                agent_id=rec.agent_id,
                policy_id=rec.policy_id,
                tool_name=rec.tool_name,
                message=rec.message,
                is_active=True,
            ))
            logger.info("drift_warning_inserted",
                        warning_type=rec.warning_type, tool_name=rec.tool_name)
        elif not existing.is_active:
            existing.is_active = True
            existing.resolved_at = None
            logger.info("drift_warning_reactivated",
                        warning_type=rec.warning_type, tool_name=rec.tool_name)

    for key, db_w in db_index.items():
        if db_w.is_active and key not in computed_keys:
            db_w.is_active = False
            db_w.resolved_at = now
            logger.info("drift_warning_auto_resolved",
                        warning_type=db_w.warning_type, tool_name=db_w.tool_name)

    await session.commit()


# ── Scheduler ─────────────────────────────────────────────────────────────────

class DriftDetector:
    def __init__(self, session_factory, interval_hours: int = 6):
        self._session_factory = session_factory
        self._interval = interval_hours * 3600
        self._task: asyncio.Task | None = None
        self.status: str = "healthy"

    def start(self) -> None:
        """Create background task (non-blocking, like OpaHealthWatcher)."""
        self._task = asyncio.create_task(self._run(), name="drift_detector")

    async def _run(self) -> None:
        await asyncio.sleep(5)   # stabilization delay
        await self.run_once()
        while True:
            await asyncio.sleep(self._interval)
            await self.run_once()

    async def run_once(self) -> None:
        try:
            async with self._session_factory() as session:
                agents = await _load_agents(session)
                policies = await _load_policies(session)
                warnings = detect_drift(agents, policies)
                await _reconcile(session, warnings)
            self.status = "healthy"
            logger.info("drift_scan_complete", warning_count=len(warnings))
        except Exception as e:
            self.status = "degraded"
            logger.error("drift_scan_failed", error=str(e))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
