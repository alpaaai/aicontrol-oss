"""
Tests: OpaHealthWatcher state machine and re-push behavior.
All tests use a mock HTTP client — no real OPA or Docker required.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch
import httpx

from app.services.opa_health_watcher import OpaHealthWatcher, OpaStatus


# --- Helpers ---

def make_ok_response(status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp

def make_404_response():
    resp = MagicMock()
    resp.status_code = 404
    resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=resp)
    )
    return resp

def make_connect_error():
    return httpx.ConnectError("Connection refused")


# --- State transition tests ---

@pytest.mark.asyncio
async def test_initial_state_is_healthy():
    """Watcher starts healthy before first poll."""
    push_fn = AsyncMock()
    watcher = OpaHealthWatcher(push_fn=push_fn, poll_interval=0)
    assert watcher.status == OpaStatus.HEALTHY


@pytest.mark.asyncio
async def test_single_failure_transitions_to_degraded():
    """One poll failure → degraded. No CRITICAL log yet."""
    push_fn = AsyncMock()
    http_client = AsyncMock()
    http_client.get = AsyncMock(side_effect=make_connect_error())

    watcher = OpaHealthWatcher(push_fn=push_fn, poll_interval=0, http_client=http_client)
    await watcher._poll_once()

    assert watcher.status == OpaStatus.DEGRADED
    assert watcher.consecutive_failures == 1


@pytest.mark.asyncio
async def test_three_failures_transitions_to_unreachable():
    """Three consecutive failures → unreachable."""
    push_fn = AsyncMock()
    http_client = AsyncMock()
    http_client.get = AsyncMock(side_effect=make_connect_error())

    watcher = OpaHealthWatcher(push_fn=push_fn, poll_interval=0, http_client=http_client)
    for _ in range(3):
        await watcher._poll_once()

    assert watcher.status == OpaStatus.UNREACHABLE
    assert watcher.consecutive_failures == 3


@pytest.mark.asyncio
async def test_recovery_from_unreachable_triggers_repush():
    """After 3 failures, one success triggers push_fn and returns to healthy."""
    push_fn = AsyncMock()
    http_client = AsyncMock()

    health_responses = [
        make_connect_error(),
        make_connect_error(),
        make_connect_error(),
        make_ok_response(200),
    ]
    bundle_response = make_ok_response(200)

    call_count = {"n": 0}
    async def mock_get(url, **kwargs):
        if "health" in url:
            resp = health_responses[call_count["n"]]
            call_count["n"] += 1
            if isinstance(resp, Exception):
                raise resp
            return resp
        else:
            return bundle_response

    http_client.get = mock_get
    watcher = OpaHealthWatcher(push_fn=push_fn, poll_interval=0, http_client=http_client)

    for _ in range(3):
        await watcher._poll_once()
    assert watcher.status == OpaStatus.UNREACHABLE

    await watcher._poll_once()
    assert watcher.status == OpaStatus.HEALTHY
    assert watcher.consecutive_failures == 0
    push_fn.assert_awaited_once()


@pytest.mark.asyncio
async def test_recovery_with_missing_bundle_triggers_repush_and_stays_degraded():
    """OPA is alive but bundle is missing (404) → push triggered, status degraded."""
    push_fn = AsyncMock()
    http_client = AsyncMock()

    async def mock_get(url, **kwargs):
        if "health" in url:
            return make_ok_response(200)
        else:
            raise httpx.HTTPStatusError(
                "404", request=MagicMock(), response=make_404_response()
            )

    http_client.get = mock_get
    watcher = OpaHealthWatcher(push_fn=push_fn, poll_interval=0, http_client=http_client)

    watcher.status = OpaStatus.DEGRADED
    watcher.consecutive_failures = 1

    await watcher._poll_once()
    push_fn.assert_awaited_once()
    assert watcher.status == OpaStatus.DEGRADED


@pytest.mark.asyncio
async def test_no_double_push_within_min_interval():
    """If push was done < 60s ago, do not push again on next recovery poll."""
    import time
    push_fn = AsyncMock()
    http_client = AsyncMock()

    async def mock_get(url, **kwargs):
        return make_ok_response(200)

    http_client.get = mock_get
    watcher = OpaHealthWatcher(push_fn=push_fn, poll_interval=0, http_client=http_client)
    watcher.status = OpaStatus.DEGRADED
    watcher.consecutive_failures = 1
    watcher._last_push_at = time.monotonic()

    await watcher._poll_once()
    push_fn.assert_not_awaited()


@pytest.mark.asyncio
async def test_healthy_poll_no_push():
    """When already healthy and OPA responds ok, push_fn is NOT called."""
    push_fn = AsyncMock()
    http_client = AsyncMock()

    async def mock_get(url, **kwargs):
        return make_ok_response(200)

    http_client.get = mock_get
    watcher = OpaHealthWatcher(push_fn=push_fn, poll_interval=0, http_client=http_client)
    await watcher._poll_once()
    push_fn.assert_not_awaited()
    assert watcher.status == OpaStatus.HEALTHY
