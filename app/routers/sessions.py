import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.core.auth import require_human
from app.models.database import async_session_factory
from app.models.schemas import AuditEvent, Session

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _=Depends(require_human),
):
    async with async_session_factory() as db:
        total = (await db.execute(select(func.count()).select_from(Session))).scalar()
        rows = (await db.execute(
            select(Session).order_by(Session.started_at.desc()).limit(limit).offset(offset)
        )).scalars().all()

    return {
        "sessions": [
            {
                "id": str(r.id),
                "agent_id": str(r.agent_id) if r.agent_id else None,
                "risk_score": r.risk_score,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
            for r in rows
        ],
        "total": total,
    }


@router.get("/{session_id}/events")
async def get_session_events(session_id: uuid.UUID, _=Depends(require_human)):
    async with async_session_factory() as db:
        session_row = (await db.execute(
            select(Session).where(Session.id == session_id)
        )).scalar_one_or_none()
        if not session_row:
            raise HTTPException(status_code=404, detail="Session not found")

        events = (await db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == session_id)
            .order_by(AuditEvent.sequence_number.asc())
        )).scalars().all()

    return {
        "session_id": str(session_id),
        "agent_id": str(session_row.agent_id) if session_row.agent_id else None,
        "risk_score": session_row.risk_score,
        "events": [
            {
                "id": str(e.id),
                "session_id": str(e.session_id),
                "tool_name": e.tool_name,
                "tool_parameters": str(e.tool_parameters)[:120] if e.tool_parameters else None,
                "decision": e.decision,
                "decision_reason": e.decision_reason,
                "policy_name": e.policy_name,
                "sequence_number": e.sequence_number,
                "duration_ms": e.duration_ms,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }
