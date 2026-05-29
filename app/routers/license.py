from fastapi import APIRouter
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
