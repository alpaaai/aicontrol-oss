"""Tests for app.core.license_gate plan-gating dependencies.

Signed-code licensing (plans/v5 2026-10-26-signed-license-keys):
get_license_info() re-verifies OrgSettings.license_key on every call and
reads plan + expiry from inside it. license_plan/license_status columns are
ignored, so writing them by hand grants nothing. No row / no code / bad
signature = community; a valid but expired code = community with
license_status "expired".
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.core.license_gate import (
    get_license_info,
    require_business_license,
    require_enterprise_license,
)
from app.models.database import async_session_factory
from tests.conftest import restore_org_settings, snapshot_org_settings


async def _set_org_settings(license_key=None, license_plan=None, license_status=None, org_name="Acme"):
    """Replace org_settings with a single known row; caller restores via
    _restore_org_settings after the test."""
    async with async_session_factory() as db:
        existing = await snapshot_org_settings(db)
        await db.execute(text("DELETE FROM org_settings"))
        await db.execute(
            text("""
                INSERT INTO org_settings (
                    id, org_name, timezone, created_at, updated_at,
                    license_plan, license_status, license_key
                )
                VALUES (
                    gen_random_uuid(), :org_name, 'UTC', now(), now(),
                    :license_plan, :license_status, :license_key
                )
            """),
            {
                "org_name": org_name,
                "license_plan": license_plan,
                "license_status": license_status,
                "license_key": license_key,
            },
        )
        await db.commit()
    return existing


async def _restore_org_settings(existing):
    async with async_session_factory() as db:
        await restore_org_settings(db, existing)
        await db.commit()


async def _assert_402(dependency):
    async with async_session_factory() as db:
        with pytest.raises(HTTPException) as exc:
            await dependency(db)
        assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_get_license_info_no_row_returns_community():
    async with async_session_factory() as db:
        existing = await snapshot_org_settings(db)
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
async def test_plan_columns_without_a_code_grant_nothing():
    existing = await _set_org_settings(license_plan="enterprise", license_status="active")
    try:
        async with async_session_factory() as db:
            info = await get_license_info(db)
        assert info.plan == "community"
        assert info.license_status is None
        await _assert_402(require_business_license)
        await _assert_402(require_enterprise_license)
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_valid_business_code_returns_its_plan_email_and_expiry(license_code):
    code = license_code("business", email="buyer@example.com")
    existing = await _set_org_settings(license_key=code, org_name="Acme")
    try:
        async with async_session_factory() as db:
            info = await get_license_info(db)
        assert info.plan == "business"
        assert info.license_status == "active"
        assert info.company == "Acme"
        assert info.email == "buyer@example.com"
        assert info.expires_at is not None
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_code_plan_wins_over_plan_columns(license_code):
    existing = await _set_org_settings(
        license_key=license_code("business"), license_plan="enterprise", license_status="active"
    )
    try:
        async with async_session_factory() as db:
            assert (await get_license_info(db)).plan == "business"
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_business_code_passes_business_402s_enterprise(license_code):
    existing = await _set_org_settings(license_key=license_code("business"))
    try:
        async with async_session_factory() as db:
            await require_business_license(db)
        await _assert_402(require_enterprise_license)
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
@pytest.mark.parametrize("plan", ["enterprise", "trial"])
async def test_enterprise_and_trial_codes_pass_both(license_code, plan):
    existing = await _set_org_settings(license_key=license_code(plan))
    try:
        async with async_session_factory() as db:
            await require_business_license(db)
        async with async_session_factory() as db:
            await require_enterprise_license(db)
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_expired_code_is_community_with_expired_status(license_code):
    existing = await _set_org_settings(license_key=license_code("enterprise", days=-1))
    try:
        async with async_session_factory() as db:
            info = await get_license_info(db)
        assert info.plan == "community"
        assert info.license_status == "expired"
        await _assert_402(require_business_license)
        await _assert_402(require_enterprise_license)
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_code_with_bad_signature_is_community(license_code):
    prefix, payload, signature = license_code("enterprise").split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    existing = await _set_org_settings(license_key=f"{prefix}.{payload}.{flipped}")
    try:
        async with async_session_factory() as db:
            info = await get_license_info(db)
        assert info.plan == "community"
        assert info.license_status is None
        await _assert_402(require_business_license)
    finally:
        await _restore_org_settings(existing)


@pytest.mark.asyncio
async def test_community_blocks_both():
    existing = await _set_org_settings()
    try:
        await _assert_402(require_business_license)
        await _assert_402(require_enterprise_license)
    finally:
        await _restore_org_settings(existing)
