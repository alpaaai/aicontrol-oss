from datetime import datetime, timedelta

import structlog
from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.models.database import async_session_factory
from app.models.user import User
from app.services.otp_service import generate_otp, verify_otp

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger()

ALGORITHM = "HS256"
HUMAN_JWT_EXPIRY_HOURS = 8


class RequestCodeBody(BaseModel):
    email: str


class VerifyCodeBody(BaseModel):
    email: str
    code: str


def _issue_human_jwt(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "type": "human",
        "exp": datetime.utcnow() + timedelta(hours=HUMAN_JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


@router.post("/request-code")
async def request_code(body: RequestCodeBody):
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.email == body.email, User.is_active == True)
        )
        user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")
    code = generate_otp(body.email)
    return {"message": "Code sent", "dev_code": code}


@router.post("/verify-code")
async def verify_code(body: VerifyCodeBody):
    if not verify_otp(body.email, body.code):
        raise HTTPException(status_code=401, detail="Invalid or expired code")
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.last_login = datetime.utcnow()
        await session.commit()
    token = _issue_human_jwt(user)
    log.info("human_login", email=user.email, role=user.role.value)
    return {"token": token, "role": user.role.value, "email": user.email}
