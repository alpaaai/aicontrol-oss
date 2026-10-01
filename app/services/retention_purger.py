"""Audit-event retention purge (Section 3.3 of plans/v4/AUDIT_AND_FIX_PLAN.md).

The pricing page promises 7-day retention for Community, 30-day for
Business, and 90-day for Enterprise/Trial. Until this module existed,
nothing enforced that -- app/routers/audit_events.py's 7-day clamp only
limited what Community could *query*, and the paid tiers had no expiry at
all (unlimited storage forever).

This is a documented, narrow exception to the Permanent Constraint that
audit_events is append-only/no-delete-ever (see .claude/CLAUDE.md) -- this
module is the ONLY place allowed to DELETE rows from audit_events or
hitl_reviews. It has exactly two sanctioned delete paths, both here so
there is one place to audit for correctness, not two that can drift:
  1. purge_expired_audit_events -- scheduled, time-cutoff purge past the
     caller's plan's advertised retention window.
  2. purge_demo_audit_events -- agent-id-scoped purge for
     app/services/demo_provisioning.py's reset_demo_agents, which resets a
     demo agent's history on request; no time cutoff, scoped to a fixed set
     of demo agent ids that never overlap real tenant data.
No other code path may delete from audit_events or hitl_reviews.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.license_gate import get_license_info
from app.core.logging import get_logger
from app.models.schemas import AuditEvent, HITLReview, Session as SessionModel

logger = get_logger("retention_purger")

RETENTION_DAYS: dict[str, int] = {
    "community": 7,
    "business": 30,
    "enterprise": 90,
    # Matches PLAN_CONFIG["trial"]["retention_days"] = 90 in
    # app/routers/billing.py -- trial mirrors enterprise's window (not a
    # separate, shorter one) so its access stays fully "Full Enterprise
    # access" with no retention divergence. Without this key,
    # .get(plan, RETENTION_DAYS["community"]) would silently fall back to
    # the 7-day community window for trial orgs.
    "trial": 90,
}


async def purge_expired_audit_events(session: AsyncSession, plan: str) -> int:
    """Delete audit_events (and any hitl_reviews referencing them) older than
    the given plan's retention window. Returns the number of audit_events
    rows deleted. hitl_reviews is deleted first -- it FK-references
    audit_event_id with no ON DELETE CASCADE, so deleting audit_events first
    would raise IntegrityError (same ordering demo_provisioning.py uses)."""
    retention_days = RETENTION_DAYS.get(plan, RETENTION_DAYS["community"])
    # AuditEvent.created_at is TIMESTAMP WITHOUT TIME ZONE (naive, UTC by
    # convention -- server_default=func.now()); comparing against a
    # tz-aware cutoff raises asyncpg.DataError.
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)

    expired_ids = (await session.execute(
        select(AuditEvent.id).where(AuditEvent.created_at < cutoff)
    )).scalars().all()
    if not expired_ids:
        return 0

    await session.execute(delete(HITLReview).where(HITLReview.audit_event_id.in_(expired_ids)))
    await session.execute(delete(AuditEvent).where(AuditEvent.id.in_(expired_ids)))
    await session.commit()
    return len(expired_ids)


async def purge_demo_audit_events(session: AsyncSession, agent_ids: list) -> int:
    """Delete audit_events (and any hitl_reviews referencing them) belonging
    to the given demo agent ids or their sessions. Second sanctioned
    exception to the audit_events append-only rule (see module docstring):
    scoped to a fixed, known set of demo agent ids, never a time cutoff and
    never caller-supplied filters. Does not delete the sessions themselves --
    the caller (app/services/demo_provisioning.py's reset_demo_agents) does
    that once audit_events/hitl_reviews referencing them are gone. Returns
    the number of audit_events rows deleted."""
    matched_ids = (await session.execute(
        select(AuditEvent.id).where(
            or_(
                AuditEvent.agent_id.in_(agent_ids),
                AuditEvent.session_id.in_(
                    select(SessionModel.id).where(SessionModel.agent_id.in_(agent_ids))
                ),
            )
        )
    )).scalars().all()
    if not matched_ids:
        return 0

    await session.execute(delete(HITLReview).where(HITLReview.audit_event_id.in_(matched_ids)))
    await session.execute(delete(AuditEvent).where(AuditEvent.id.in_(matched_ids)))
    await session.commit()
    return len(matched_ids)


class RetentionPurger:
    """Background scheduler, same shape as enterprise/app/services/drift_detector.DriftDetector."""

    def __init__(self, session_factory, interval_hours: int = 24):
        self._session_factory = session_factory
        self._interval = interval_hours * 3600
        self._task: "asyncio.Task | None" = None
        self.status: str = "healthy"

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="retention_purger")

    async def _run(self) -> None:
        await asyncio.sleep(5)  # stabilization delay, matches DriftDetector
        await self.run_once()
        while True:
            await asyncio.sleep(self._interval)
            await self.run_once()

    async def run_once(self) -> None:
        try:
            async with self._session_factory() as session:
                try:
                    plan = (await get_license_info(session)).plan
                except HTTPException:
                    # A set-but-invalid/expired license key must not crash the
                    # purge loop, but it also must not guess a plan for a
                    # destructive delete -- skip this cycle rather than risk
                    # purging a paying customer's data under community's
                    # shorter window because their key glitched.
                    logger.warning("retention_purge_skipped_invalid_license")
                    self.status = "degraded"
                    return
                deleted = await purge_expired_audit_events(session, plan)
            self.status = "healthy"
            logger.info("retention_purge_complete", plan=plan, deleted=deleted)
        except Exception as e:
            self.status = "degraded"
            logger.error("retention_purge_failed", error=str(e))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
