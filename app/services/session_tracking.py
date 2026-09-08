"""Session bookkeeping shared by app/routers/intercept.py and the MCP gateway
(app/routers/mcp_gateway.py, plan 02) — moved here so plan 04 can delete
app/routers/intercept.py without breaking the gateway's import of these."""
import uuid

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import Session

RISK_SCORE_DELTA: dict[str, int] = {
    "allow": 1,
    "review": 10,
    "deny": 25,
}


async def ensure_session(db: AsyncSession, session_id: uuid.UUID, agent_id: uuid.UUID) -> None:
    """Create a session row if one does not already exist for this session_id."""
    from sqlalchemy import select

    result = await db.execute(select(Session).where(Session.id == session_id))
    if result.scalar_one_or_none() is not None:
        return
    try:
        async with db.begin_nested():
            db.add(Session(id=session_id, agent_id=agent_id, status="active"))
            await db.flush()
    except IntegrityError:
        pass


async def accumulate_session_risk(db: AsyncSession, session_id: uuid.UUID, delta: int) -> None:
    """Add delta to sessions.risk_score for this session. No-op if delta is 0."""
    if delta == 0:
        return
    await db.execute(
        update(Session).where(Session.id == session_id).values(risk_score=Session.risk_score + delta)
    )
