"""POST /agents/{agent_id}/coverage — adapter install-time handshake.

Nothing checked in the market research answers "your check is installed but
never fires." The handshake separates "this agent has never run" from "this
agent ran and the hook never fired", which traffic alone cannot distinguish.

Goes to the customer's own self-hosted API, not to us. Nothing leaves their
infrastructure.
"""
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_agent
from app.core.logging import get_logger
from app.models.database import get_db
from app.models.schemas import Agent

router = APIRouter(tags=["coverage"])
logger = get_logger("coverage")


class CoverageHandshake(BaseModel):
    framework: str
    hook: str
    sdk_version: str
    workflow: str = "unassigned"
    agent_name: str | None = None
    silent_noop_warnings: list[str] = []


class CoverageResponse(BaseModel):
    agent_id: uuid.UUID
    coverage_state: str


@router.post("/agents/{agent_id}/coverage", response_model=CoverageResponse)
async def report_coverage(
    agent_id: uuid.UUID,
    body: CoverageHandshake,
    db: AsyncSession = Depends(get_db),
    token: dict = Depends(require_agent),
) -> CoverageResponse:
    if token.get("role") == "agent" and token.get("agent_id") is not None:
        if str(token["agent_id"]) != str(agent_id):
            raise HTTPException(403, "Token is scoped to a different agent")

    agent = (await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )).scalar_one_or_none()

    if agent is None:
        # D14: auto-register. An agent that is live but unregistered is exactly
        # the blind spot this feature exists to close -- 404ing would keep it
        # invisible. observe mode, always: auto-registration must never begin
        # enforcing against an agent nobody configured.
        agent = Agent(
            id=agent_id,
            name=body.agent_name or f"unregistered-{agent_id}",
            owner="unregistered",
            status="active",
            governance_mode="observe",
        )
        db.add(agent)
        logger.info(
            "agent_auto_registered_from_handshake",
            agent_id=str(agent_id), framework=body.framework,
        )

    agent.framework = body.framework
    agent.hook = body.hook
    agent.sdk_version = body.sdk_version
    agent.workflow = body.workflow
    agent.silent_noop_warnings = body.silent_noop_warnings
    # Naive UTC: every TIMESTAMP column in this schema is WITHOUT TIME ZONE,
    # and asyncpg refuses an aware datetime for one.
    agent.coverage_last_seen_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    await db.commit()

    if body.silent_noop_warnings:
        logger.warning(
            "adapter_silent_noop_risk",
            agent_id=str(agent_id), framework=body.framework,
            warnings=body.silent_noop_warnings,
        )

    return CoverageResponse(agent_id=agent_id, coverage_state="governed")
