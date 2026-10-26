"""
FastAPI dependencies for plan-gating.

Signed-code licensing (plans/v5 2026-10-26-signed-license-keys):
get_license_info() re-verifies OrgSettings.license_key with
app/core/license_key.py on every call and takes plan + expiry from inside
the code. license_plan/license_status columns are not read, so editing them
grants nothing. No row / no code / bad signature = community; a valid code
past its expiry = community with license_status "expired".

Usage in routers:
    @router.get("/endpoint", dependencies=[Depends(require_enterprise_license)])
    async def endpoint(): ...

    @router.get("/endpoint", dependencies=[Depends(require_business_license)])
    async def endpoint(): ...

Correct test patching:
    from app.core import license_gate
    with patch.object(license_gate, "get_license_info", return_value=mock_info):
        ...
    # OR:
    app.dependency_overrides[require_enterprise_license] = lambda: None
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.license_key import decode_license_code
from app.models.database import get_db
from app.models.user import OrgSettings


class LicenseError(Exception):
    """Raised when a license cannot be validated."""
    pass


@dataclass
class LicenseInfo:
    plan: str           # "community" | "business" | "enterprise" | "trial"
    company: Optional[str]
    email: Optional[str]
    expires_at: Optional[datetime]
    # "active" (verified, unexpired code) | "expired" (verified code past its
    # expiry; plan falls back to community) | None (no code, or a code that
    # does not verify).
    license_status: Optional[str] = None

    @property
    def is_enterprise(self) -> bool:
        return self.plan in ("enterprise", "trial")

    @property
    def is_business(self) -> bool:
        return self.plan in ("business", "enterprise", "trial")

    def to_dict(self) -> dict:
        return {
            "plan": self.plan,
            "company": self.company,
            "email": self.email,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_enterprise": self.is_enterprise,
            "is_business": self.is_business,
        }


async def get_license_info(db: AsyncSession) -> LicenseInfo:
    """
    Read the current license from the single OrgSettings row's signed
    license_key, re-verified on every call (signature check is cached per
    code string in license_key; expiry is compared here every time).

    Returns LicenseInfo(plan="community") when no row exists, no code is
    stored, or the code doesn't verify.
    """
    result = await db.execute(select(OrgSettings).limit(1))
    org = result.scalar_one_or_none()
    payload = decode_license_code(org.license_key) if org is not None and org.license_key else None
    if payload is None:
        return LicenseInfo(plan="community", company=None, email=None, expires_at=None)
    if payload.is_expired(datetime.now(timezone.utc)):
        return LicenseInfo(
            plan="community",
            company=org.org_name,
            email=payload.email,
            expires_at=payload.expires_at,
            license_status="expired",
        )
    return LicenseInfo(
        plan=payload.plan,
        company=org.org_name,
        email=payload.email,
        expires_at=payload.expires_at,
        license_status="active",
    )


async def has_enterprise_license(db: AsyncSession) -> bool:
    """Plain boolean check for call sites that need to branch on plan rather
    than raise -- e.g. the demo harness, which must decide whether to run a
    paid-tier beat at all instead of letting it 402."""
    return (await get_license_info(db)).is_enterprise


def _paid_plan_is_active(info: LicenseInfo) -> bool:
    """A business/enterprise plan only counts as usable when its status is
    'active' -- get_license_info sets that only for a verified, unexpired
    license code."""
    return info.license_status == "active"


async def require_enterprise_license(db: AsyncSession = Depends(get_db)) -> None:
    """
    FastAPI dependency. Raises HTTP 402 if plan is not 'enterprise' with an
    active license_status.
    Use as: dependencies=[Depends(require_enterprise_license)]
    """
    info = await get_license_info(db)
    if not info.is_enterprise or not _paid_plan_is_active(info):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "enterprise_required",
                "message": "This feature requires an Enterprise license.",
                "current_plan": info.plan,
                "action": "Contact enterprise@aictl.io to upgrade.",
            },
        )


async def require_business_license(db: AsyncSession = Depends(get_db)) -> None:
    """
    FastAPI dependency. Raises HTTP 402 if plan is 'community', or if
    business/enterprise but license_status isn't 'active'.
    Use as: dependencies=[Depends(require_business_license)]
    """
    info = await get_license_info(db)
    if not info.is_business or not _paid_plan_is_active(info):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "business_required",
                "message": "This feature requires a Business or Enterprise license.",
                "current_plan": info.plan,
                "action": "Contact enterprise@aictl.io to upgrade.",
            },
        )
