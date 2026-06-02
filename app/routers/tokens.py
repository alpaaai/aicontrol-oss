"""POST /tokens — admin-authenticated token issuance with optional agent scoping."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_token, hash_token, require_admin
from app.models.database import get_db
from app.models.schemas import APIToken, Agent

router = APIRouter(prefix="/tokens", tags=["tokens"])


class TokenCreateRequest(BaseModel):
    role: str
    description: str
    agent_id: Optional[uuid.UUID] = None


class TokenCreateResponse(BaseModel):
    token_id: uuid.UUID
    role: str
    description: str
    agent_id: Optional[uuid.UUID]
    token: str


class TokenListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    description: Optional[str]
    agent_id: Optional[uuid.UUID]
    agent_name: Optional[str]
    revoked: bool
    created_at: Optional[datetime]


@router.get("", response_model=list[TokenListItem])
async def list_tokens(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[TokenListItem]:
    q = (
        select(APIToken, Agent.name.label("agent_name"))
        .outerjoin(Agent, APIToken.agent_id == Agent.id)
        .order_by(APIToken.created_at.desc())
    )
    if active_only:
        q = q.where(APIToken.revoked == False)  # noqa: E712

    rows = (await db.execute(q)).all()
    return [
        TokenListItem(
            id=r.APIToken.id,
            role=r.APIToken.role,
            description=r.APIToken.description,
            agent_id=r.APIToken.agent_id,
            agent_name=r.agent_name,
            revoked=r.APIToken.revoked,
            created_at=r.APIToken.created_at,
        )
        for r in rows
    ]


@router.post("", response_model=TokenCreateResponse)
async def create_agent_token(
    body: TokenCreateRequest,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> TokenCreateResponse:
    """Issue a new token. If agent_id is provided, revokes any prior active token for that agent."""
    if body.role not in ("agent", "admin"):
        raise HTTPException(status_code=400, detail="role must be 'agent' or 'admin'")

    if body.agent_id is not None:
        # Verify agent exists
        agent = await db.get(Agent, body.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Revoke any prior active token for this agent
        await db.execute(
            update(APIToken)
            .where(
                APIToken.agent_id == body.agent_id,
                APIToken.revoked == False,
            )
            .values(revoked=True)
        )

    raw_token = create_token(role=body.role, description=body.description)
    token_hash = hash_token(raw_token)

    db_token = APIToken(
        token_hash=token_hash,
        role=body.role,
        description=body.description,
        agent_id=body.agent_id,
        revoked=False,
    )
    db.add(db_token)
    await db.flush()
    await db.commit()

    return TokenCreateResponse(
        token_id=db_token.id,
        role=db_token.role,
        description=db_token.description,
        agent_id=db_token.agent_id,
        token=raw_token,
    )
