import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, exists

from app.core.auth import require_human
from app.models.database import async_session_factory
from app.models.schemas import Agent, AuditEvent, HITLReview, Session

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _=Depends(require_human),
):
    event_count_sq = (
        select(func.count())
        .where(AuditEvent.session_id == Session.id)
        .correlate(Session)
        .scalar_subquery()
    )
    pending_review_sq = (
        select(exists().where(
            (HITLReview.session_id == Session.id) &
            (HITLReview.status == "pending")
        ))
        .correlate(Session)
        .scalar_subquery()
    )

    async with async_session_factory() as db:
        total = (await db.execute(select(func.count()).select_from(Session))).scalar()
        rows = (await db.execute(
            select(
                Session,
                Agent.name.label("agent_name"),
                event_count_sq.label("event_count"),
                pending_review_sq.label("has_pending_review"),
            )
            .outerjoin(Agent, Session.agent_id == Agent.id)
            .order_by(Session.started_at.desc())
            .limit(limit)
            .offset(offset)
        )).all()

    return {
        "sessions": [
            {
                "id": str(r.Session.id),
                "agent_id": str(r.Session.agent_id) if r.Session.agent_id else None,
                "agent_name": r.agent_name,
                "status": r.Session.status,
                "started_at": r.Session.started_at.isoformat() if r.Session.started_at else None,
                "completed_at": r.Session.completed_at.isoformat() if r.Session.completed_at else None,
                "event_count": r.event_count or 0,
                "has_pending_review": bool(r.has_pending_review),
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
        "trigger_context": session_row.trigger_context,
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
