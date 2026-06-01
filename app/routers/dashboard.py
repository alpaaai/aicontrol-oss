from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text

from app.core.auth import require_human
from app.models.database import async_session_factory
from app.models.schemas import Agent, AuditEvent, HITLReview, Policy, Session
from app.models.user import UserActivityLog

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_summary(_=Depends(require_human)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    async with async_session_factory() as db:
        def _count(since):
            return select(func.count()).select_from(AuditEvent).where(AuditEvent.created_at >= since)

        intercepts_today = (await db.execute(_count(today_start))).scalar()
        intercepts_7d = (await db.execute(_count(week_start))).scalar()
        intercepts_30d = (await db.execute(_count(month_start))).scalar()

        decision_rows = (await db.execute(
            select(AuditEvent.decision, func.count())
            .where(AuditEvent.created_at >= today_start)
            .group_by(AuditEvent.decision)
        )).all()
        decisions = {d: c for d, c in decision_rows}
        allow_today = decisions.get("allow", 0)
        deny_today = decisions.get("deny", 0)
        review_today = decisions.get("review", 0)
        deny_rate = round(deny_today / intercepts_today * 100, 1) if intercepts_today else 0.0

        active_sessions = (await db.execute(
            select(func.count()).select_from(Session)
            .where(Session.started_at >= now - timedelta(hours=1))
        )).scalar()

        pending_reviews = (await db.execute(
            select(func.count()).select_from(HITLReview)
            .where(HITLReview.status == "pending")
        )).scalar()

        active_agents = (await db.execute(
            select(func.count()).select_from(Agent).where(Agent.status == "active")
        )).scalar()

        active_policies = (await db.execute(
            select(func.count()).select_from(Policy).where(Policy.active == True)
        )).scalar()

        top_tools_rows = (await db.execute(
            select(AuditEvent.tool_name, func.count().label("count"))
            .where(AuditEvent.created_at >= now - timedelta(hours=24))
            .group_by(AuditEvent.tool_name)
            .order_by(text("count DESC"))
            .limit(10)
        )).all()
        top_tools = [{"tool": t, "count": c} for t, c in top_tools_rows]

        hours_rows = (await db.execute(
            select(
                func.date_trunc("hour", AuditEvent.created_at).label("hour"),
                AuditEvent.decision,
                func.count().label("count"),
            )
            .where(AuditEvent.created_at >= now - timedelta(hours=24))
            .group_by("hour", AuditEvent.decision)
            .order_by("hour")
        )).all()
        decisions_by_hour = [
            {"hour": h.isoformat(), "decision": d, "count": c}
            for h, d, c in hours_rows
        ]

    return {
        "intercepts_today": intercepts_today,
        "intercepts_7d": intercepts_7d,
        "intercepts_30d": intercepts_30d,
        "allow_count_today": allow_today,
        "deny_count_today": deny_today,
        "review_count_today": review_today,
        "deny_rate_today": deny_rate,
        "active_sessions": active_sessions,
        "pending_reviews": pending_reviews,
        "active_agents": active_agents,
        "active_policies": active_policies,
        "top_tools": top_tools,
        "decisions_by_hour": decisions_by_hour,
    }


@router.get("/activity-log")
async def list_activity_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    _=Depends(require_human),
):
    async with async_session_factory() as db:
        q = select(UserActivityLog)
        cq = select(func.count()).select_from(UserActivityLog)
        if action:
            q = q.where(UserActivityLog.action == action)
            cq = cq.where(UserActivityLog.action == action)
        if date_from:
            dt = datetime.fromisoformat(date_from)
            q = q.where(UserActivityLog.created_at >= dt)
            cq = cq.where(UserActivityLog.created_at >= dt)
        if date_to:
            dt = datetime.fromisoformat(date_to)
            q = q.where(UserActivityLog.created_at < dt + timedelta(days=1))
            cq = cq.where(UserActivityLog.created_at < dt + timedelta(days=1))
        total = (await db.execute(cq)).scalar()
        rows = (await db.execute(
            q.order_by(UserActivityLog.created_at.desc()).limit(limit).offset(offset)
        )).scalars().all()
    return {
        "logs": [
            {
                "id": str(r.id),
                "user_email": r.user_email,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "before_state": r.before_state,
                "after_state": r.after_state,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": total,
    }
