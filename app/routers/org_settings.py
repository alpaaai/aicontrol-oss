"""GET /org-settings and PUT /org-settings."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_human, require_human_admin
from app.models.database import get_db
from app.models.user import OrgSettings
from app.services.billing_client import BillingClientError, sync_license

router = APIRouter(prefix="/org-settings", tags=["org-settings"])

# Separate router: path is /settings/license-activation, not
# /org-settings/... (plans/v4 task 23) -- distinct prefix, same file since
# it shares org_settings.py's auth/DB conventions.
settings_router = APIRouter(prefix="/settings", tags=["settings"])


class OrgSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    org_name: str
    timezone: str


class UpdateOrgSettingsBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    org_name: str
    timezone: str

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, KeyError):
            raise ValueError(f"Unknown timezone: {v}")
        return v


@router.get("", response_model=OrgSettingsResponse)
async def get_org_settings(
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_human),
):
    result = await db.execute(select(OrgSettings).limit(1))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Org settings not configured")
    return org


@router.put("", response_model=OrgSettingsResponse)
async def update_org_settings(
    body: UpdateOrgSettingsBody,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_human),
):
    result = await db.execute(select(OrgSettings).limit(1))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Org settings not configured")
    org.org_name = body.org_name
    org.timezone = body.timezone
    await db.commit()
    await db.refresh(org)
    return org


class LicenseActivationBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    activation_code: str


class LicenseActivationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    license_status: str | None
    license_plan: str | None
    license_synced_at: datetime | None


@settings_router.put("/license-activation", response_model=LicenseActivationResponse)
async def activate_license(
    body: LicenseActivationBody,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_human_admin),
):
    """Only way an activation code enters the system (plans/v4 task 23,
    scope decision 4 -- BillingPage.tsx only, no install.sh prompt).
    Validates against billing-service before saving: a code that doesn't
    work is never stored."""
    try:
        result = await sync_license(body.activation_code)
    except BillingClientError:
        raise HTTPException(status_code=400, detail="Invalid activation code")

    org_result = await db.execute(select(OrgSettings).limit(1))
    org = org_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Org settings not configured")

    org.activation_code = body.activation_code
    org.license_status = result["status"]
    org.license_plan = result["plan"]
    org.license_synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(org)
    return org
