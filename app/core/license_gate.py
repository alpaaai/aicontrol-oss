"""
License gate for enterprise features.
Simple: any non-empty AICONTROL_LICENSE_KEY = enterprise unlocked.

Usage in routers:
    from fastapi import Depends
    from app.core.license_gate import require_enterprise_license

    @router.get("/enterprise/feature", dependencies=[Depends(require_enterprise_license)])
    async def enterprise_feature():
        ...
"""
from fastapi import HTTPException, status
from app.core.config import settings


def require_enterprise_license() -> None:
    if not settings.AICONTROL_LICENSE_KEY:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "enterprise_license_required",
                "message": "This feature requires an AIControl Enterprise license.",
                "info": "https://aictl.io/pricing"
            }
        )


def generate_license_key(customer_id: str, tier: str) -> str:
    """Stub: simple key generation for onboarding. No-touch provisioning."""
    import secrets
    return f"aictl_{tier}_{customer_id}_{secrets.token_urlsafe(16)}"
