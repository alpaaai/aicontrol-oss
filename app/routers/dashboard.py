from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select, text

from app.core.auth import require_human
from app.models.database import async_session_factory
from app.models.schemas import Agent, AuditEvent, HITLReview, Policy, Session
from app.models.user import UserActivityLog
from app.models.policy_warning import PolicyWarning

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
                func.date_trunc("day", AuditEvent.created_at).label("hour"),
                AuditEvent.decision,
                func.count().label("count"),
            )
            .where(AuditEvent.created_at >= now - timedelta(days=30))
            .group_by("hour", AuditEvent.decision)
            .order_by("hour")
        )).all()
        decisions_by_hour = [
            {"hour": h.isoformat(), "decision": d, "count": c}
            for h, d, c in hours_rows
        ]

        active_warnings = (await db.execute(
            select(func.count()).select_from(PolicyWarning)
            .where(PolicyWarning.is_active == True)
        )).scalar()

        overdue_reviews = (await db.execute(
            select(func.count()).select_from(HITLReview)
            .where(HITLReview.status == "pending")
            .where(HITLReview.response_deadline < now)
        )).scalar()

        top_deny_row = (await db.execute(
            select(AuditEvent.tool_name, func.count().label("cnt"))
            .where(AuditEvent.created_at >= today_start)
            .where(AuditEvent.decision == "deny")
            .group_by(AuditEvent.tool_name)
            .order_by(text("cnt DESC"))
            .limit(1)
        )).first()
        top_denied_tool = (
            {"tool": top_deny_row.tool_name, "count": top_deny_row.cnt}
            if top_deny_row else None
        )

        high_risk_sessions = (await db.execute(
            select(func.count()).select_from(Session)
            .where(Session.risk_score > 50)
            .where(Session.started_at >= now - timedelta(hours=1))
        )).scalar()

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
        "active_warnings": active_warnings,
        "overdue_reviews": overdue_reviews,
        "top_denied_tool": top_denied_tool,
        "high_risk_sessions": high_risk_sessions,
    }


@router.get("/metrics")
async def get_metrics(_=Depends(require_human)):
    now = datetime.utcnow()
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    async with async_session_factory() as db:
        total_7d = (await db.execute(
            select(func.count()).select_from(AuditEvent)
            .where(AuditEvent.created_at >= week_start)
        )).scalar()

        policy_hits_7d = (await db.execute(
            select(func.count()).select_from(AuditEvent)
            .where(AuditEvent.created_at >= week_start)
            .where(AuditEvent.policy_id.isnot(None))
        )).scalar()

        policy_hit_rate = round(policy_hits_7d / total_7d * 100, 1) if total_7d else 0.0

        deny_trend_rows = (await db.execute(
            select(
                func.date_trunc("day", AuditEvent.created_at).label("day"),
                AuditEvent.decision,
                func.count().label("count"),
            )
            .where(AuditEvent.created_at >= month_start)
            .group_by("day", AuditEvent.decision)
            .order_by("day")
        )).all()
        deny_trend = [
            {"day": r.day.isoformat(), "decision": r.decision, "count": r.count}
            for r in deny_trend_rows
        ]

        agent_deny_rows = (await db.execute(
            select(
                AuditEvent.agent_name,
                func.count().label("total"),
                func.sum(
                    case((AuditEvent.decision == "deny", 1), else_=0)
                ).label("denies"),
            )
            .where(AuditEvent.created_at >= week_start)
            .where(AuditEvent.agent_name.isnot(None))
            .group_by(AuditEvent.agent_name)
            .order_by(text("denies DESC"))
            .limit(10)
        )).all()
        top_agents_by_deny_rate = [
            {
                "agent_name": r.agent_name,
                "total": r.total,
                "deny_rate": round(r.denies / r.total * 100, 1) if r.total else 0.0,
            }
            for r in agent_deny_rows
        ]

        avg_resolution = (await db.execute(
            select(func.avg(
                func.extract("epoch", HITLReview.reviewed_at - HITLReview.created_at)
            ))
            .where(HITLReview.status.in_(["approved", "denied"]))
            .where(HITLReview.reviewed_at.isnot(None))
        )).scalar()
        avg_review_seconds = round(float(avg_resolution), 0) if avg_resolution else None

    return {
        "policy_hit_rate": policy_hit_rate,
        "deny_trend": deny_trend,
        "top_agents_by_deny_rate": top_agents_by_deny_rate,
        "avg_review_seconds": avg_review_seconds,
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
