"""Agent registration CRUD — admin only."""
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.logging import get_logger
from app.models.database import get_db
from app.models.schemas import Agent, APIToken, AuditEvent

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


class AgentUpdate(BaseModel):
    owner: Optional[str] = None
    framework: Optional[str] = None
    model_version: Optional[str] = None
    system_prompt_hash: Optional[str] = None
    approved_tools: Optional[list[str]] = None
    status: Optional[str] = None
    approved_by: Optional[str] = None

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


class ApprovedToolsUpdate(BaseModel):
    approved_tools: list[str]


class ApprovedToolsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: uuid.UUID
    approved_tools: list[str]


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
            last_active_sq.label("last_active"),
            total_sq.label("total_count"),
            deny_sq.label("deny_count"),
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
    return agent


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
