"""First-run setup endpoints — public, no auth required."""
import hashlib
import os
import uuid
from datetime import datetime, timedelta

import re

import structlog
from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func, select

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

from app.core.config import settings
from app.models.database import async_session_factory
from app.models.user import OrgSettings, User, UserRole

router = APIRouter(prefix="/setup", tags=["setup"])
log = structlog.get_logger()

ALGORITHM = "HS256"
HUMAN_JWT_EXPIRY_HOURS = 8


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + dk.hex()


def _issue_human_jwt(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "type": "human",
        "exp": datetime.utcnow() + timedelta(hours=HUMAN_JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


class SetupCompleteBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str
    email: str
    password: str
    org_name: str
    timezone: str

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("org_name")
    @classmethod
    def org_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("org_name must not be empty")
        return v

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, v: str) -> str:
        try:
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            ZoneInfo(v)
        except (KeyError, Exception):
            raise ValueError(f"'{v}' is not a valid IANA timezone")
        return v


@router.get("/status")
async def setup_status():
    async with async_session_factory() as db:
        result = await db.execute(select(func.count()).select_from(User))
        count = result.scalar()
    return {"setup_required": count == 0}


@router.post("/complete")
async def setup_complete(body: SetupCompleteBody):
    async with async_session_factory() as db:
        result = await db.execute(select(func.count()).select_from(User))
        if result.scalar() > 0:
            raise HTTPException(status_code=409, detail="Setup has already been completed")

        user = User(
            id=uuid.uuid4(),
            email=body.email,
            name=body.full_name,
            role=UserRole.admin,
            is_active=True,
            is_root=True,
            password_hash=_hash_password(body.password),
            password_set=True,
        )
        db.add(user)

        org = OrgSettings(
            id=uuid.uuid4(),
            org_name=body.org_name,
            timezone=body.timezone,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(org)
        await db.commit()
        await db.refresh(user)

    token = _issue_human_jwt(user)
    log.info("setup_complete", email=user.email)
    return {
        "token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.name,
            "role": user.role.value,
        },
    }
