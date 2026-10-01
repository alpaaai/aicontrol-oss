"""Tests for app.core.license_gate plan-gating dependencies.

DB-backed (plans/v4 task 15): get_license_info() reads OrgSettings directly
-- no row / no license_plan = community, matching the old empty-key default.
require_business_license / require_enterprise_license gate on both plan
tier and license_status: for business/enterprise plans, license_status !=
"active" also fails the check.
"""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.core.license_gate import (
    get_license_info,
    require_business_license,
    require_enterprise_license,
)
from app.models.database import async_session_factory


async def _set_org_settings(license_plan=None, license_status=None, org_name="Acme"):
    """Replace org_settings with a single known row; caller restores via
    _restore_org_settings after the test."""
    async with async_session_factory() as db:
        saved = await db.execute(text("SELECT id, org_name, timezone FROM org_settings"))
        existing = saved.fetchall()
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(
            text("""
                INSERT INTO org_settings (
                    id, org_name, timezone, created_at, updated_at,
                    license_plan, license_status
                )
                VALUES (
                    gen_random_uuid(), :org_name, 'UTC', now(), now(),
                    :license_plan, :license_status
                )
            """),
            {"org_name": org_name, "license_plan": license_plan, "license_status": license_status},
        )
        await db.commit()
    return existing


async def _restore_org_settings(existing):
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM org_settings"))
        for row in existing:
            await db.execute(
                text("""
                    INSERT INTO org_settings (id, org_name, timezone, created_at, updated_at)
                    VALUES (:id, :name, :tz, now(), now())
                    ON CONFLICT DO NOTHING
                """),
                {"id": str(row[0]), "name": row[1], "tz": row[2]},
            )
        await db.commit()


@pytest.mark.asyncio
async def test_get_license_info_no_row_returns_community():
    async with async_session_factory() as db:
        saved = await db.execute(text("SELECT id, org_name, timezone FROM org_settings"))
        existing = saved.fetchall()
        await db.execute(text("DELETE FROM org_settings"))
        await db.commit()
    try:
        async with async_session_factory() as db:
            info = await get_license_info(db)
        assert info.plan == "community"
        assert info.license_status is None
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_get_license_info_active_business():
    existing = await _set_org_settings(license_plan="business", license_status="active", org_name="Acme")
    try:
        async with async_session_factory() as db:
            info = await get_license_info(db)
        assert info.plan == "business"
        assert info.license_status == "active"
        assert info.company == "Acme"
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_business_plan_active_status_passes_business_402s_enterprise():
    existing = await _set_org_settings(license_plan="business", license_status="active")
    try:
        async with async_session_factory() as db:
            await require_business_license(db)
        async with async_session_factory() as db:
            with pytest.raises(HTTPException) as exc:
                await require_enterprise_license(db)
            assert exc.value.status_code == 402
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_business_plan_past_due_status_402s_both():
    existing = await _set_org_settings(license_plan="business", license_status="past_due")
    try:
        async with async_session_factory() as db:
            with pytest.raises(HTTPException) as exc:
                await require_business_license(db)
            assert exc.value.status_code == 402
        async with async_session_factory() as db:
            with pytest.raises(HTTPException) as exc:
                await require_enterprise_license(db)
            assert exc.value.status_code == 402
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_enterprise_plan_canceled_status_402s_both():
    existing = await _set_org_settings(license_plan="enterprise", license_status="canceled")
    try:
        async with async_session_factory() as db:
            with pytest.raises(HTTPException) as exc:
                await require_business_license(db)
            assert exc.value.status_code == 402
        async with async_session_factory() as db:
            with pytest.raises(HTTPException) as exc:
                await require_enterprise_license(db)
            assert exc.value.status_code == 402
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_enterprise_plan_active_status_passes_both():
    existing = await _set_org_settings(license_plan="enterprise", license_status="active")
    try:
        async with async_session_factory() as db:
            await require_business_license(db)
        async with async_session_factory() as db:
            await require_enterprise_license(db)
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_community_blocks_both():
    existing = await _set_org_settings(license_plan=None, license_status=None)
    try:
        async with async_session_factory() as db:
            with pytest.raises(HTTPException) as exc:
                await require_business_license(db)
            assert exc.value.status_code == 402
        async with async_session_factory() as db:
            with pytest.raises(HTTPException) as exc:
                await require_enterprise_license(db)
            assert exc.value.status_code == 402
    finally:
        await _restore_org_settings(existing)
