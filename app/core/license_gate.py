"""
FastAPI dependencies for plan-gating.

DB-backed (plans/v4 task 15): get_license_info() reads the single
OrgSettings row directly -- no RS256, no PUBLIC_KEY, no signed license-key
env var. No row / no license_plan set = community, matching the old
empty-key-decodes-to-community default.

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
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    # DB-status-based licensing (plans/v4 task 15): "active" | "past_due" |
    # "canceled" | None (never synced / community). None only for a business
    # or enterprise plan that hasn't synced yet -- community always has this
    # unset since it has no subscription to have a status.
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
    Read the current license from the single OrgSettings row.

    Returns LicenseInfo(plan="community") when no row exists or no
    license_plan is set.
    """
    result = await db.execute(select(OrgSettings).limit(1))
    org = result.scalar_one_or_none()
    if org is None or not org.license_plan:
        return LicenseInfo(plan="community", company=None, email=None, expires_at=None)
    return LicenseInfo(
        plan=org.license_plan,
        company=org.org_name,
        email=None,
        expires_at=None,
        license_status=org.license_status,
    )


async def has_enterprise_license(db: AsyncSession) -> bool:
    """Plain boolean check for call sites that need to branch on plan rather
    than raise -- e.g. the demo harness, which must decide whether to run a
    paid-tier beat at all instead of letting it 402."""
    return (await get_license_info(db)).is_enterprise


def _paid_plan_is_active(info: LicenseInfo) -> bool:
    """A business/enterprise plan only counts as usable when its synced
    status is 'active' -- past_due/canceled (or never-synced None) must
    402 the same as community, no grace period."""
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
