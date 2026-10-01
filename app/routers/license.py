from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import license_gate
from app.core.auth import require_human
from app.core.license_gate import get_license_info
from app.models.database import get_db

router = APIRouter(tags=["license"])


@router.get("/license-info")
async def license_info(db: AsyncSession = Depends(get_db)):
    """
    Returns current license plan metadata.
    Public endpoint — no authentication required.
    Used by the React frontend to determine which features to render.
    Never returns the raw JWT or sensitive fields.
    """
    info = await get_license_info(db)
    return {
        "plan": info.plan,
        "company": info.company,
        "is_enterprise": info.is_enterprise,
        "is_business": info.is_business,
        "expires_at": info.expires_at.isoformat() if info.expires_at else None,
    }


class FeatureFlags(BaseModel):
    nl_authoring: bool
    simulation: bool
    hitl: bool
    compliance_reports: bool


class LicenseFeatures(BaseModel):
    tier: str
    features: FeatureFlags
    # plans/v4 task 17: "active" | "past_due" | "canceled" | None. None means
    # either community (never subscribed) or a business/enterprise plan that
    # hasn't synced yet. Lets the frontend tell "never subscribed" (tier
    # alone decides nav visibility, unchanged) apart from "had business/
    # enterprise, now past_due/canceled" (same tier as when active, so the
    # frontend can render a reactivate banner instead of hiding the nav).
    license_status: str | None


@router.get("/license/features", response_model=LicenseFeatures)
async def license_features(
    _=Depends(require_human), db: AsyncSession = Depends(get_db)
) -> LicenseFeatures:
    """Which destinations exist for this install. The nav renders from this:
    a paid destination is absent on a free install, never locked or greyed.
    tier reflects the plan the org is licensed for regardless of
    license_status, so a past_due/canceled business org still sees its
    business nav items (task 25 routes them to a reactivate banner instead
    of hiding them)."""
    info = await license_gate.get_license_info(db)
    tier = "enterprise" if info.is_enterprise else "business" if info.is_business else "free"
    return LicenseFeatures(
        tier=tier,
        features=FeatureFlags(
            nl_authoring=info.is_enterprise, simulation=info.is_enterprise,
            hitl=info.is_business, compliance_reports=info.is_enterprise,
        ),
        license_status=info.license_status,
    )
