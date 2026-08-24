"""Agent registration CRUD — admin only, except /register (agent or admin — see below)."""
import json
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, case, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin, require_agent
from app.core.logging import get_logger
from app.models.database import get_db
from app.models.schemas import Agent, APIToken, AuditEvent, Policy

router = APIRouter(prefix="/agents", tags=["agents"])
logger = get_logger("agents_api")


class AgentCreate(BaseModel):
    name: str
    owner: str
    framework: Optional[str] = None
    model_version: Optional[str] = None
    system_prompt_hash: Optional[str] = None
    approved_tools: list[str] = []
    metadata: dict[str, Any] = {}
    governance_mode: Optional[Literal["observe", "govern"]] = None


class AgentUpdate(BaseModel):
    owner: Optional[str] = None
    framework: Optional[str] = None
    model_version: Optional[str] = None
    system_prompt_hash: Optional[str] = None
    approved_tools: Optional[list[str]] = None
    status: Optional[str] = None
    approved_by: Optional[str] = None
    governance_mode: Optional[Literal["observe", "govern"]] = None

    @field_validator("status")
    @classmethod
    def _status_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"active", "suspended"}:
            raise ValueError("status must be 'active' or 'suspended'")
        return v


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    owner: str
    status: str
    framework: Optional[str]
    model_version: Optional[str]
    approved_tools: list
    approved_by: Optional[str]
    governance_mode: str
    hook: Optional[str] = None
    sdk_version: Optional[str] = None
    workflow: Optional[str] = None
    coverage_last_seen_at: Optional[datetime] = None
    coverage_state: str = "unknown"
    silent_noop_warnings: list = []
    unresolved_systems: list = []


class AgentListItem(BaseModel):
    id: uuid.UUID
    name: str
    owner: str
    status: str
    framework: Optional[str]
    model_version: Optional[str]
    approved_tools: list
    approved_by: Optional[str]
    system_prompt_hash: Optional[str]
    approved_at: Optional[datetime]
    created_at: Optional[datetime]
    last_active: Optional[datetime]
    deny_rate: Optional[float]
    hook: Optional[str] = None
    sdk_version: Optional[str] = None
    workflow: Optional[str] = None
    coverage_last_seen_at: Optional[datetime] = None
    coverage_state: str = "unknown"
    silent_noop_warnings: list = []
    unresolved_systems: list = []


def derive_coverage_state(agent: Any, has_recent_traffic: bool) -> str:
    """installed_not_firing is the state this feature exists to surface: the
    library loaded and the hook bound, but no call ever arrived."""
    if agent.coverage_last_seen_at is None:
        return "unknown"
    return "governed" if has_recent_traffic else "installed_not_firing"


class ApprovedToolsUpdate(BaseModel):
    approved_tools: list[str]


class ApprovedToolsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: uuid.UUID
    approved_tools: list[str]


class AgentRegisterRequest(BaseModel):
    name: str
    owner: str = "sdk-auto-registered"
    framework: Optional[str] = None
    approved_tools: list[str] = []


@router.post("/register", response_model=AgentResponse)
async def register_agent(
    body: AgentRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_agent),
) -> AgentResponse:
    """Zero-friction SDK self-registration: idempotent get-or-create by name.

    Open to agent-role tokens (not admin-only) so instrument() can register
    an agent on first call with no separate onboarding step. Returns 201 for
    a freshly created agent, 200 when one with this name already existed.
    """
    new_id = uuid.uuid4()
    result = await db.execute(
        text("""
            INSERT INTO agents (id, name, owner, status, framework, approved_tools)
            VALUES (:id, :name, :owner, 'active', :framework, CAST(:tools AS jsonb))
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id, (xmax = 0) AS inserted
        """),
        {
            "id": str(new_id),
            "name": body.name,
            "owner": body.owner,
            "framework": body.framework,
            "tools": json.dumps(body.approved_tools),
        },
    )
    row = result.one()
    await db.commit()
    response.status_code = 201 if row.inserted else 200
    logger.info("agent_self_registered", agent_id=str(row.id), name=body.name, created=row.inserted)
    return await db.get(Agent, row.id)


@router.get("", response_model=list[AgentListItem])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[AgentListItem]:
    last_active_sq = (
        select(func.max(AuditEvent.created_at))
        .where(AuditEvent.agent_id == Agent.id)
        .correlate(Agent)
        .scalar_subquery()
    )
    total_sq = (
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.agent_id == Agent.id)
        .correlate(Agent)
        .scalar_subquery()
    )
    deny_sq = (
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.agent_id == Agent.id, AuditEvent.decision == "deny")
        .correlate(Agent)
        .scalar_subquery()
    )

    # One correlated EXISTS for every agent, not one query per agent.
    recent_traffic_sq = (
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.agent_id == Agent.id,
            AuditEvent.created_at >= Agent.coverage_last_seen_at,
        )
        .correlate(Agent)
        .scalar_subquery()
    )

    rows = (await db.execute(
        select(
            Agent.id,
            Agent.name,
            Agent.owner,
            Agent.status,
            Agent.framework,
            Agent.model_version,
            Agent.approved_tools,
            Agent.approved_by,
            Agent.system_prompt_hash,
            Agent.approved_at,
            Agent.created_at,
            Agent.hook,
            Agent.sdk_version,
            Agent.workflow,
            Agent.coverage_last_seen_at,
            Agent.silent_noop_warnings,
            Agent.unresolved_systems,
            last_active_sq.label("last_active"),
            total_sq.label("total_count"),
            deny_sq.label("deny_count"),
            recent_traffic_sq.label("recent_traffic_count"),
        ).order_by(Agent.name)
    )).all()

    return [
        AgentListItem(
            id=r.id,
            name=r.name,
            owner=r.owner,
            status=r.status,
            framework=r.framework,
            model_version=r.model_version,
            approved_tools=r.approved_tools or [],
            approved_by=r.approved_by,
            system_prompt_hash=r.system_prompt_hash,
            approved_at=r.approved_at,
            created_at=r.created_at,
            last_active=r.last_active,
            deny_rate=round(r.deny_count / r.total_count, 4) if r.total_count else None,
            hook=r.hook,
            sdk_version=r.sdk_version,
            workflow=r.workflow,
            coverage_last_seen_at=r.coverage_last_seen_at,
            coverage_state=derive_coverage_state(r, bool(r.recent_traffic_count)),
            silent_noop_warnings=r.silent_noop_warnings or [],
            unresolved_systems=r.unresolved_systems or [],
        )
        for r in rows
    ]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> AgentResponse:
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    has_recent_traffic = False
    if agent.coverage_last_seen_at is not None:
        has_recent_traffic = bool((await db.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.agent_id == agent.id,
                AuditEvent.created_at >= agent.coverage_last_seen_at,
            )
        )).scalar())

    response = AgentResponse.model_validate(agent)
    response.coverage_state = derive_coverage_state(agent, has_recent_traffic)
    response.silent_noop_warnings = agent.silent_noop_warnings or []
    response.unresolved_systems = agent.unresolved_systems or []
    return response


class AgentPolicyResponse(BaseModel):
    """Shaped as the frontend's PolicyScope, not the raw `policies` columns --
    this endpoint feeds the agent's governing-policies list directly, so it
    skips the snake_case-to-camelCase mapper every other policy consumer uses."""

    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    principal_type: Optional[str] = Field(None, alias="principalType")
    principal_id: Optional[str] = Field(None, alias="principalId")
    action_tool: Optional[str] = Field(None, alias="actionTool")
    resource_system: Optional[str] = Field(None, alias="resourceSystem")
    effect: str
    condition: dict[str, Any]


@router.get("/{agent_id}/policies", response_model=list[AgentPolicyResponse], response_model_by_alias=True)
async def get_agent_policies(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[AgentPolicyResponse]:
    """Every policy whose principal matches this agent -- the same scope the
    /intercept pre-filter applies, minus the tool and system filters."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    principal_match = or_(
        Policy.principal_id.is_(None),
        and_(Policy.principal_type == "agent", Policy.principal_id == agent.name),
    )
    result = await db.execute(
        select(Policy).where(Policy.active == True, principal_match)  # noqa: E712
    )
    return [
        AgentPolicyResponse(
            id=p.id,
            principal_type=p.principal_type,
            principal_id=p.principal_id,
            action_tool=p.action_tool,
            resource_system=p.resource_system,
            effect=p.effect or "deny",
            condition=p.condition,
        )
        for p in result.scalars().all()
    ]


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> AgentResponse:
    agent = Agent(
        name=body.name,
        owner=body.owner,
        framework=body.framework,
        model_version=body.model_version,
        system_prompt_hash=body.system_prompt_hash,
        approved_tools=body.approved_tools,
        status="active",
        metadata_=body.metadata,
        **({"governance_mode": body.governance_mode} if body.governance_mode else {}),
    )
    db.add(agent)
    await db.flush()
    logger.info("agent_created", agent_id=str(agent.id), name=agent.name)
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> AgentResponse:
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(agent, field, value)
    await db.flush()
    logger.info("agent_updated", agent_id=str(agent_id))
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> None:
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    logger.info("agent_deleted", agent_id=str(agent_id))


@router.patch("/{agent_id}/approved-tools", response_model=ApprovedToolsResponse)
async def update_approved_tools(
    agent_id: uuid.UUID,
    body: ApprovedToolsUpdate,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> ApprovedToolsResponse:
    """Replace an agent's approved_tools list. Full replace semantics — send complete new list."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.approved_tools = body.approved_tools
    await db.commit()
    await db.refresh(agent)

    logger.info("approved_tools_updated", agent_id=str(agent_id), count=len(body.approved_tools))
    return ApprovedToolsResponse(
        agent_id=agent.id,
        approved_tools=agent.approved_tools or [],
    )


@router.delete("/{agent_id}/token", status_code=200)
async def revoke_agent_token(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> dict:
    """Revoke all active tokens scoped to this agent."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        update(APIToken)
        .where(APIToken.agent_id == agent_id, APIToken.revoked == False)
        .values(revoked=True)
        .returning(APIToken.id)
    )
    revoked_ids = result.scalars().all()
    await db.commit()

    if not revoked_ids:
        raise HTTPException(status_code=404, detail="No active token found for this agent")

    logger.info("agent_token_revoked", agent_id=str(agent_id), count=len(revoked_ids))
    return {"revoked": len(revoked_ids)}
