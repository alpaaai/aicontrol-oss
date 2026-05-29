"""
FastAPI dependencies for plan-gating.

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
from fastapi import Depends, HTTPException

from app.core.license import LicenseError, LicenseInfo, decode_license_key
from app.core.config import settings


def get_license_info() -> LicenseInfo:
    """
    Decode and return the current license.

    Returns LicenseInfo(plan="community") when no key is set.
    Raises HTTPException(402) when the key is set but invalid/expired.

    Plain function (not async, not a FastAPI dependency itself) so it can be
    called from startup code and patched in tests without dependency_overrides.
    """
    try:
        return decode_license_key(settings.AICONTROL_LICENSE_KEY)
    except LicenseError as e:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "license_error",
                "message": str(e),
                "action": "Contact enterprise@aictl.io to resolve your license.",
            },
        )


def require_enterprise_license() -> None:
    """
    FastAPI dependency. Raises HTTP 402 if plan is not 'enterprise'.
    Use as: dependencies=[Depends(require_enterprise_license)]
    """
    info = get_license_info()
    if not info.is_enterprise:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "enterprise_required",
                "message": "This feature requires an Enterprise license.",
                "current_plan": info.plan,
                "action": "Contact enterprise@aictl.io to upgrade.",
            },
        )


def require_business_license() -> None:
    """
    FastAPI dependency. Raises HTTP 402 if plan is 'community'.
    Business and Enterprise plans both pass.
    Use as: dependencies=[Depends(require_business_license)]
    """
    info = get_license_info()
    if not info.is_business:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "business_required",
                "message": "This feature requires a Business or Enterprise license.",
                "current_plan": info.plan,
                "action": "Contact enterprise@aictl.io to upgrade.",
            },
        )
