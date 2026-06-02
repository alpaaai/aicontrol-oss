"""GET /org-settings and PUT /org-settings."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_human
from app.models.database import get_db
from app.models.user import OrgSettings

router = APIRouter(prefix="/org-settings", tags=["org-settings"])


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
