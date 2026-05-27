"""OPA Health-Watch Loop — P1-4

Polls OPA every OPA_POLL_INTERVAL_SECONDS seconds.
Two-step check per poll:
  1. GET /health — is the OPA process alive?
  2. GET /v1/policies/aicontrol — is our bundle loaded?

State machine:
  healthy    → any failure      → degraded  (log WARNING)
  degraded   → 3rd failure      → unreachable (log CRITICAL)
  any state  → success (both checks pass) → healthy + re-push if previously unhealthy

Re-push dampening: min 60 seconds between pushes to suppress flap noise.
"""
import asyncio
import enum
import time
from typing import Callable, Awaitable, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("opa_health_watcher")

MIN_PUSH_INTERVAL_SECONDS = 60
UNREACHABLE_THRESHOLD = 3


class OpaStatus(str, enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"


class OpaHealthWatcher:
    """
    Background asyncio task that watches OPA health and triggers policy re-push
    on recovery.

    Args:
        push_fn: Async callable that re-pushes policies to OPA. Injected for testability.
        poll_interval: Seconds between polls. Defaults to settings.opa_poll_interval_seconds.
        http_client: Optional injected async HTTP client for testing.
    """

    def __init__(
        self,
        push_fn: Callable[[], Awaitable[None]],
        poll_interval: Optional[int] = None,
        http_client=None,
    ):
        self.push_fn = push_fn
        self.poll_interval = (
            poll_interval
            if poll_interval is not None
            else settings.opa_poll_interval_seconds
        )
        self._http_client = http_client
        self.status: OpaStatus = OpaStatus.HEALTHY
        self.consecutive_failures: int = 0
        self._last_push_at: float = 0.0
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Schedule the poll loop as a background asyncio task."""
        self._task = asyncio.create_task(self._run(), name="opa_health_watcher")
        log.info("opa_health_watcher_started", poll_interval=self.poll_interval)

    async def stop(self) -> None:
        """Cancel the background task gracefully."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("opa_health_watcher_stopped")

    @property
    def opa_status(self) -> str:
        """String value for the /health endpoint response."""
        return self.status.value

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.poll_interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Execute one health check cycle. Public for testing."""
        opa_alive = await self._check_opa_alive()

        if not opa_alive:
            self._handle_failure()
            return

        bundle_loaded = await self._check_bundle_loaded()

        if not bundle_loaded:
            prev_status = self.status
            self.status = OpaStatus.DEGRADED
            self.consecutive_failures = max(1, self.consecutive_failures)
            log.warning(
                "opa_bundle_missing",
                previous_status=prev_status,
                action="triggering_repush",
            )
            await self._maybe_push()
            return

        was_unhealthy = self.status != OpaStatus.HEALTHY
        prev_status = self.status
        self.status = OpaStatus.HEALTHY
        self.consecutive_failures = 0

        if was_unhealthy:
            log.info(
                "opa_recovered",
                previous_status=prev_status,
                action="repushing_policies",
            )
            await self._maybe_push()

    async def _check_opa_alive(self) -> bool:
        try:
            resp = await self._http_client.get(
                f"{settings.opa_url}/health", timeout=5.0
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            log.debug("opa_health_check_failed", error=str(exc))
            return False

    async def _check_bundle_loaded(self) -> bool:
        try:
            resp = await self._http_client.get(
                f"{settings.opa_url}/v1/policies/aicontrol", timeout=5.0
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return False
            log.warning("opa_bundle_check_unexpected_error", error=str(exc))
            return False
        except Exception as exc:
            log.debug("opa_bundle_check_failed", error=str(exc))
            return False

    def _handle_failure(self) -> None:
        self.consecutive_failures += 1

        if self.consecutive_failures == 1:
            prev = self.status
            self.status = OpaStatus.DEGRADED
            log.warning(
                "opa_health_degraded",
                consecutive_failures=self.consecutive_failures,
                previous_status=prev,
            )

        elif self.consecutive_failures >= UNREACHABLE_THRESHOLD:
            if self.status != OpaStatus.UNREACHABLE:
                self.status = OpaStatus.UNREACHABLE
                log.critical(
                    "opa_unreachable",
                    consecutive_failures=self.consecutive_failures,
                    failure_mode=settings.opa_failure_mode,
                    message=(
                        "OPA has been unreachable for "
                        f"{self.consecutive_failures} consecutive polls. "
                        f"Intercept is fail-{settings.opa_failure_mode}."
                    ),
                )

    async def _maybe_push(self) -> None:
        """Push policies to OPA unless a push happened recently (flap dampening)."""
        now = time.monotonic()
        if now - self._last_push_at < MIN_PUSH_INTERVAL_SECONDS:
            log.debug(
                "opa_repush_skipped_too_soon",
                seconds_since_last_push=int(now - self._last_push_at),
            )
            return

        try:
            await self.push_fn()
            self._last_push_at = now
            log.info("opa_policies_repushed")
        except Exception as exc:
            log.error("opa_repush_failed", error=str(exc))
