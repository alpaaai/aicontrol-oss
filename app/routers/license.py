from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core import license_gate
from app.core.auth import require_human
from app.core.license_gate import get_license_info

router = APIRouter(tags=["license"])


@router.get("/license-info")
async def license_info():
    """
    Returns current license plan metadata.
    Public endpoint — no authentication required.
    Used by the React frontend to determine which features to render.
    Never returns the raw JWT or sensitive fields.
    """
    info = get_license_info()
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


@router.get("/license/features", response_model=LicenseFeatures)
async def license_features(_=Depends(require_human)) -> LicenseFeatures:
    """Which destinations exist for this install. The nav renders from this:
    a paid destination is absent on a free install, never locked or greyed."""
    paid = license_gate.get_license_info().is_enterprise
    return LicenseFeatures(
        tier="enterprise" if paid else "free",
        features=FeatureFlags(
            nl_authoring=paid, simulation=paid,
            hitl=paid, compliance_reports=paid,
        ),
    )
