"""Tests for the org_settings licensing/activation-code columns added by
the org_settings licensing migration (plans/v4 task 14)."""
import uuid
from datetime import datetime, timezone

import pytest

from app.models.database import async_session_factory
from app.models.user import OrgSettings


@pytest.mark.asyncio
async def test_org_settings_licensing_columns_round_trip():
    async with async_session_factory() as db:
        row = OrgSettings(
            id=uuid.uuid4(),
            org_name="Licensing Test Org",
            license_plan="business",
            license_status="active",
            license_synced_at=datetime.now(timezone.utc).replace(tzinfo=None),
            activation_code="aicontrol-test-activation-code",
        )
        db.add(row)
        await db.commit()
        row_id = row.id

    async with async_session_factory() as db:
        fetched = await db.get(OrgSettings, row_id)
        assert fetched.license_plan == "business"
        assert fetched.license_status == "active"
        assert fetched.license_synced_at is not None
        assert fetched.activation_code == "aicontrol-test-activation-code"
        await db.delete(fetched)
        await db.commit()


@pytest.mark.asyncio
async def test_org_settings_licensing_columns_are_nullable():
    async with async_session_factory() as db:
        row = OrgSettings(id=uuid.uuid4(), org_name="No License Org")
        db.add(row)
        await db.commit()
        row_id = row.id

    async with async_session_factory() as db:
        fetched = await db.get(OrgSettings, row_id)
        assert fetched.license_plan is None
        assert fetched.license_status is None
        assert fetched.license_synced_at is None
        assert fetched.activation_code is None
        await db.delete(fetched)
        await db.commit()
