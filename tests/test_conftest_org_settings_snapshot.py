"""snapshot_org_settings/restore_org_settings must round-trip every
org_settings column, including the license and activation_code columns the
older per-file restores dropped."""
import pytest
from sqlalchemy import text

from app.models.database import async_session_factory
from tests.conftest import restore_org_settings, snapshot_org_settings


@pytest.mark.asyncio
async def test_snapshot_restore_round_trips_every_column():
    async with async_session_factory() as db:
        original = await snapshot_org_settings(db)
    try:
        async with async_session_factory() as db:
            await db.execute(text("DELETE FROM org_settings"))
            await db.execute(text("""
                INSERT INTO org_settings (
                    id, org_name, timezone, created_at, updated_at,
                    license_plan, license_status, license_synced_at, activation_code
                ) VALUES (
                    gen_random_uuid(), 'pytest-snapshot-org', 'UTC',
                    '2026-01-02 03:04:05+00', '2026-02-03 04:05:06+00',
                    'enterprise', 'active', '2026-03-04 05:06:07+00', 'pytest-code'
                )
            """))
            await db.commit()

        async with async_session_factory() as db:
            before = await snapshot_org_settings(db)
            await db.execute(text("DELETE FROM org_settings"))
            await db.commit()

        async with async_session_factory() as db:
            await restore_org_settings(db, before)
            await db.commit()

        async with async_session_factory() as db:
            after = await snapshot_org_settings(db)

        assert len(before) == 1
        assert after == before
        assert after[0]["license_plan"] == "enterprise"
        assert after[0]["activation_code"] == "pytest-code"
    finally:
        async with async_session_factory() as db:
            await restore_org_settings(db, original)
            await db.commit()
