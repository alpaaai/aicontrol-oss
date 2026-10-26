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
    # "active" | "expired" | None. None means no code, or one that does not
    # verify. An expired code reports tier "free" with status "expired".
    license_status: str | None


@router.get("/license/features", response_model=LicenseFeatures)
async def license_features(
    _=Depends(require_human), db: AsyncSession = Depends(get_db)
) -> LicenseFeatures:
    """Which destinations exist for this install. The nav renders from this:
    a paid destination is absent on a free install, never locked or greyed.
    tier comes from get_license_info, so an expired code is "free"."""
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
