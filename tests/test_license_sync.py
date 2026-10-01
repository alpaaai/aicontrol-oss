"""Tests for app/services/license_sync.py -- the daily background job that
syncs OrgSettings.license_status/license_plan from billing-service using
the org's stored activation code (plans/v4 task 20)."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.billing_client import BillingClientError
from app.services.license_sync import LicenseSync


def _org(activation_code=None, license_synced_at=None, license_status=None, license_plan=None):
    return SimpleNamespace(
        activation_code=activation_code,
        license_synced_at=license_synced_at,
        license_status=license_status,
        license_plan=license_plan,
    )


def _session_factory_mock(org):
    """A session factory whose session.execute(...).scalar_one_or_none()
    returns the given org row, matching get_license_info()'s own query
    shape (a single OrgSettings row via db.execute(select(...)))."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = org
    mock_session.execute.return_value = mock_result
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=mock_session)
    return factory, mock_session


@pytest.mark.asyncio
async def test_run_once_skips_and_does_not_call_billing_client_when_no_activation_code():
    org = _org(activation_code=None)
    factory, mock_session = _session_factory_mock(org)

    with patch("app.services.license_sync.sync_license", new_callable=AsyncMock) as mock_sync:
        job = LicenseSync(factory, interval_hours=24)
        await job.run_once()
        mock_sync.assert_not_called()
    assert job.status == "healthy"


@pytest.mark.asyncio
async def test_successful_sync_writes_status_plan_and_synced_at():
    org = _org(activation_code="test-code", license_status="active", license_plan="business",
               license_synced_at=datetime.now(timezone.utc) - timedelta(days=1))
    factory, mock_session = _session_factory_mock(org)

    with patch("app.services.license_sync.sync_license", new_callable=AsyncMock,
               return_value={"status": "active", "plan": "enterprise"}):
        job = LicenseSync(factory, interval_hours=24)
        await job.run_once()

    assert org.license_status == "active"
    assert org.license_plan == "enterprise"
    assert org.license_synced_at is not None
    assert (datetime.now(timezone.utc) - org.license_synced_at) < timedelta(seconds=5)
    mock_session.commit.assert_called()
    assert job.status == "healthy"


@pytest.mark.asyncio
async def test_sync_failure_within_grace_period_keeps_last_known_status():
    """3 days since last successful sync -- fail-open, status unchanged."""
    org = _org(activation_code="test-code", license_status="active", license_plan="business",
               license_synced_at=datetime.now(timezone.utc) - timedelta(days=3))
    factory, mock_session = _session_factory_mock(org)

    with patch("app.services.license_sync.sync_license", new_callable=AsyncMock,
               side_effect=BillingClientError("billing-service unreachable")):
        job = LicenseSync(factory, interval_hours=24)
        await job.run_once()

    assert org.license_status == "active"
    assert org.license_plan == "business"


@pytest.mark.asyncio
async def test_sync_failure_past_grace_period_forces_status_unreachable():
    """8 days since last successful sync -- fail-closed."""
    org = _org(activation_code="test-code", license_status="active", license_plan="business",
               license_synced_at=datetime.now(timezone.utc) - timedelta(days=8))
    factory, mock_session = _session_factory_mock(org)

    with patch("app.services.license_sync.sync_license", new_callable=AsyncMock,
               side_effect=BillingClientError("billing-service unreachable")):
        job = LicenseSync(factory, interval_hours=24)
        await job.run_once()

    assert org.license_status == "unreachable"


@pytest.mark.asyncio
async def test_successful_canceled_response_applies_immediately_regardless_of_sync_recency():
    org = _org(activation_code="test-code", license_status="active", license_plan="business",
               license_synced_at=datetime.now(timezone.utc))
    factory, mock_session = _session_factory_mock(org)

    with patch("app.services.license_sync.sync_license", new_callable=AsyncMock,
               return_value={"status": "canceled", "plan": "business"}):
        job = LicenseSync(factory, interval_hours=24)
        await job.run_once()

    assert org.license_status == "canceled"


@pytest.mark.asyncio
async def test_no_org_settings_row_is_a_noop():
    factory, mock_session = _session_factory_mock(None)

    with patch("app.services.license_sync.sync_license", new_callable=AsyncMock) as mock_sync:
        job = LicenseSync(factory, interval_hours=24)
        await job.run_once()
        mock_sync.assert_not_called()
    assert job.status == "healthy"


@pytest.mark.asyncio
async def test_stop_cancels_task():
    org = _org(activation_code=None)
    factory, mock_session = _session_factory_mock(org)

    with patch("app.services.license_sync.sync_license", new_callable=AsyncMock), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        job = LicenseSync(factory, interval_hours=24)
        job.start()
        await asyncio.sleep(0)
        await job.stop()
        assert job._task is None or job._task.cancelled()
