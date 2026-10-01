"""Daily background license sync against billing-service (plans/v4 task 20).

The only outbound network call this plan adds to a customer's self-hosted
deployment -- keeps OrgSettings.license_status/license_plan in sync with
billing-service's view so annual renewal requires zero manual customer
action. Only runs when OrgSettings.activation_code is set; community
installs skip it entirely.

Fail-open on an unreachable billing-service (keep the last-known-good
status) unless it has been more than MISSED_SYNC_GRACE_DAYS since the last
successful sync, in which case fail closed -- license_status is forced to
UNREACHABLE_STATUS, which require_business_license/require_enterprise_license
treat the same as an inactive subscription. Deriving the missed-sync count
from license_synced_at's age (rather than a separate counter column) means
"7 consecutive missed daily syncs" can't drift out of sync with what
actually happened.

A successful sync response of "canceled" is applied immediately regardless
of how recent the last sync was -- the 7-day grace period is only for
unreachability, never for a genuine cancellation response.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.logging import get_logger
from app.models.user import OrgSettings
from app.services.billing_client import BillingClientError, sync_license

logger = get_logger("license_sync")

MISSED_SYNC_GRACE_DAYS = 7
UNREACHABLE_STATUS = "unreachable"


class LicenseSync:
    """Background scheduler, same shape as
    app/services/retention_purger.RetentionPurger."""

    def __init__(self, session_factory, interval_hours: int = 24):
        self._session_factory = session_factory
        self._interval = interval_hours * 3600
        self._task: "asyncio.Task | None" = None
        self.status: str = "healthy"

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="license_sync")

    async def _run(self) -> None:
        await asyncio.sleep(5)  # stabilization delay, matches RetentionPurger
        await self.run_once()
        while True:
            await asyncio.sleep(self._interval)
            await self.run_once()

    async def run_once(self) -> None:
        try:
            async with self._session_factory() as session:
                org = (
                    await session.execute(select(OrgSettings).limit(1))
                ).scalar_one_or_none()
                if org is None or not org.activation_code:
                    self.status = "healthy"
                    return

                try:
                    result = await sync_license(org.activation_code)
                except BillingClientError as exc:
                    logger.warning("license_sync_unreachable", error=str(exc))
                    self._apply_missed_sync(org)
                    await session.commit()
                    self.status = "degraded"
                    return

                org.license_status = result["status"]
                org.license_plan = result["plan"]
                org.license_synced_at = datetime.now(timezone.utc)
                await session.commit()
            self.status = "healthy"
            logger.info("license_sync_complete", status=result["status"], plan=result["plan"])
        except Exception as e:
            self.status = "degraded"
            logger.error("license_sync_failed", error=str(e))

    def _apply_missed_sync(self, org: OrgSettings) -> None:
        last_synced = org.license_synced_at
        if last_synced is not None and last_synced.tzinfo is None:
            last_synced = last_synced.replace(tzinfo=timezone.utc)
        grace_exceeded = (
            last_synced is None
            or datetime.now(timezone.utc) - last_synced > timedelta(days=MISSED_SYNC_GRACE_DAYS)
        )
        if grace_exceeded:
            org.license_status = UNREACHABLE_STATUS

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
