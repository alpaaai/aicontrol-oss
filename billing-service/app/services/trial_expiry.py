"""Trial expiry background job (plans/v4 trial-refund-pricing task 9).

A one-time $1 trial checkout generates no further Stripe events -- nothing
else counts down or reverts a trial's 90 days of enterprise-tier access.
This job is that countdown: it reverts any billing_customers row whose
trial_expires_at has passed back to Community.

Same shape as app/services/license_sync.LicenseSync, itself the same shape
as app/services/retention_purger.RetentionPurger in the aicontrol repo.

subscription_status is set to 'expired' rather than reusing Stripe's own
'canceled' -- aicontrol's frontend treats 'canceled' as "show the
reactivate-via-Stripe-Portal banner", which doesn't apply to a trial that
simply ran out and reverted to the always-free Community tier.
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.logging import get_logger
from app.models import BillingCustomer

logger = get_logger("trial_expiry")


class TrialExpiry:
    def __init__(self, session_factory, interval_hours: int = 1):
        self._session_factory = session_factory
        self._interval = interval_hours * 3600
        self._task: "asyncio.Task | None" = None
        self.status: str = "healthy"

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="trial_expiry")

    async def _run(self) -> None:
        await asyncio.sleep(5)  # stabilization delay, matches LicenseSync/RetentionPurger
        await self.run_once()
        while True:
            await asyncio.sleep(self._interval)
            await self.run_once()

    async def run_once(self) -> None:
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(BillingCustomer).where(
                        BillingCustomer.plan == "trial",
                        BillingCustomer.trial_expires_at < datetime.now(timezone.utc),
                    )
                )
                expired = result.scalars().all()
                for customer in expired:
                    customer.plan = "community"
                    customer.subscription_status = "expired"
                await session.commit()
            self.status = "healthy"
            logger.info("trial_expiry_complete", reverted=len(expired))
        except Exception as e:
            self.status = "degraded"
            logger.error("trial_expiry_failed", error=str(e))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
