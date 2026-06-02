import hashlib
from datetime import datetime, timedelta

import structlog
from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core.config import settings
from app.models.database import async_session_factory
from app.models.user import User
from app.routers.setup import _hash_password

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger()

ALGORITHM = "HS256"
HUMAN_JWT_EXPIRY_HOURS = 8


def _issue_human_jwt(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "type": "human",
        "exp": datetime.utcnow() + timedelta(hours=HUMAN_JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a scrypt hash (salt:hash format)."""
    try:
        salt_hex, hash_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
        return actual == expected
    except Exception:
        return False


class LoginBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: str
    password: str


@router.post("/login")
async def login(body: LoginBody):
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.email == body.email.lower())
        )
        user = result.scalar_one_or_none()

    if user is None or not user.password_hash or not _verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == body.email.lower()))
        user = result.scalar_one()
        user.last_login = datetime.utcnow()
        await session.commit()
        await session.refresh(user)

    token = _issue_human_jwt(user)
    log.info("human_login", email=user.email, role=user.role.value)
    return {
        "token": token,
        "user": {"id": str(user.id), "email": user.email, "full_name": user.name, "role": user.role.value},
        "first_login": not user.password_set,
    }
