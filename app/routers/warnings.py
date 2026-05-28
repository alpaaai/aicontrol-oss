"""Warnings router: GET /warnings, PATCH /warnings/{id}/resolve."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.license_gate import require_enterprise_license
from app.core.logging import get_logger
from app.models.database import get_db
from app.models.policy_warning import PolicyWarning
from app.models.schemas import Agent, Policy

router = APIRouter(prefix="/warnings", tags=["warnings"])
logger = get_logger("warnings_api")


class WarningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    warning_type: str
    agent_id: Optional[uuid.UUID]
    agent_name: Optional[str]
    policy_id: Optional[uuid.UUID]
    policy_name: Optional[str]
    tool_name: str
    message: str
    is_active: bool
    created_at: datetime
    resolved_at: Optional[datetime]


async def _enrich(
    session: AsyncSession, warnings: list[PolicyWarning]
) -> list[WarningResponse]:
    """Join agent_name and policy_name for display."""
    agent_ids = {w.agent_id for w in warnings if w.agent_id}
    policy_ids = {w.policy_id for w in warnings if w.policy_id}

    agents: dict = {}
    if agent_ids:
        result = await session.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        agents = {a.id: a.name for a in result.scalars().all()}

    policies: dict = {}
    if policy_ids:
        result = await session.execute(select(Policy).where(Policy.id.in_(policy_ids)))
        policies = {p.id: p.name for p in result.scalars().all()}

    return [
        WarningResponse(
            id=w.id,
            warning_type=w.warning_type,
            agent_id=w.agent_id,
            agent_name=agents.get(w.agent_id) if w.agent_id else None,
            policy_id=w.policy_id,
            policy_name=policies.get(w.policy_id) if w.policy_id else None,
            tool_name=w.tool_name,
            message=w.message,
            is_active=w.is_active,
            created_at=w.created_at,
            resolved_at=w.resolved_at,
        )
        for w in warnings
    ]


@router.get("", response_model=list[WarningResponse], dependencies=[Depends(require_enterprise_license)])
async def list_warnings(
    is_active: Optional[bool] = Query(default=True),
    warning_type: Optional[str] = Query(default=None),
    agent_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[WarningResponse]:
    q = select(PolicyWarning)
    if is_active is not None:
        q = q.where(PolicyWarning.is_active == is_active)
    if warning_type:
        q = q.where(PolicyWarning.warning_type == warning_type)
    if agent_id:
        q = q.where(PolicyWarning.agent_id == agent_id)
    q = q.order_by(PolicyWarning.created_at.desc())
    result = await db.execute(q)
    warnings = result.scalars().all()
    return await _enrich(db, warnings)


@router.patch("/{warning_id}/resolve", response_model=WarningResponse, dependencies=[Depends(require_enterprise_license)])
async def resolve_warning(
    warning_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> WarningResponse:
    result = await db.execute(
        select(PolicyWarning).where(PolicyWarning.id == warning_id)
    )
    warning = result.scalar_one_or_none()
    if not warning:
        raise HTTPException(status_code=404, detail="Warning not found")

    warning.is_active = False
    warning.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(warning)

    logger.info("warning_resolved", warning_id=str(warning_id))
    enriched = await _enrich(db, [warning])
    return enriched[0]
