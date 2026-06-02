from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select

from app.core.auth import require_human
from app.core import license_gate as _lg
from app.models.database import async_session_factory
from app.models.schemas import AuditEvent

router = APIRouter(prefix="/audit-events", tags=["audit-events"])


@router.get("")
async def list_audit_events(
    decision: Optional[str] = Query(None, pattern="^(allow|deny|review)$"),
    agent_id: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _=Depends(require_human),
):
    # Community plan: enforce 7-day retention at query layer
    license_info = _lg.get_license_info()
    if license_info.plan == "community":
        retention_cutoff = datetime.utcnow() - timedelta(days=7)
        if date_from is None or date_from < retention_cutoff:
            date_from = retention_cutoff

    filters = []
    if decision:
        filters.append(AuditEvent.decision == decision)
    if agent_id:
        filters.append(AuditEvent.agent_id == agent_id)
    if tool_name:
        filters.append(AuditEvent.tool_name.ilike(f"%{tool_name}%"))
    if date_from:
        filters.append(AuditEvent.created_at >= date_from)
    if date_to:
        filters.append(AuditEvent.created_at <= date_to)

    where = and_(*filters) if filters else True

    async with async_session_factory() as session:
        total = (await session.execute(
            select(func.count()).select_from(AuditEvent).where(where)
        )).scalar()
        rows = (await session.execute(
            select(AuditEvent).where(where)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit).offset(offset)
        )).scalars().all()

    return {
        "events": [
            {
                "id": str(r.id),
                "session_id": str(r.session_id),
                "agent_id": str(r.agent_id),
                "agent_name": r.agent_name,
                "tool_name": r.tool_name,
                "tool_parameters": str(r.tool_parameters)[:120] if r.tool_parameters else None,
                "decision": r.decision,
                "decision_reason": r.decision_reason,
                "policy_id": str(r.policy_id) if r.policy_id else None,
                "policy_name": r.policy_name,
                "duration_ms": r.duration_ms,
                "sequence_number": r.sequence_number,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
