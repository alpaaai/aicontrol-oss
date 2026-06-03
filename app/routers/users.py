"""User management endpoints — list, create, update, delete, invite."""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.config import settings
from app.models.database import get_db, async_session_factory
from app.models.user import User, UserRole
from app.services.invite_service import generate_invite_token

router = APIRouter(prefix="/users", tags=["users"])

INVITE_EXPIRY_HOURS = 24


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    is_root: bool
    password_set: bool
    last_login: Optional[datetime]
    created_at: datetime


class CreateUserBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    full_name: str
    email: str
    role: str


class UpdateUserBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    is_active: Optional[bool] = None
    role: Optional[str] = None


def _magic_link(token: str) -> str:
    return f"{settings.FRONTEND_BASE_URL}/invite?token={token}"


def _user_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.name,
        "role": user.role.value,
    }


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
) -> list[UserResponse]:
    result = await db.execute(select(User).order_by(User.email))
    return result.scalars().all()


@router.post("", status_code=201)
async def create_user(
    body: CreateUserBody,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
):
    # validate role
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid role: {body.role}")

    result = await db.execute(select(User).where(User.email == body.email.lower()))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already exists")

    token, token_hash = generate_invite_token()
    expires_at = datetime.utcnow() + timedelta(hours=INVITE_EXPIRY_HOURS)

    user = User(
        email=body.email.lower(),
        name=body.full_name,
        role=role,
        is_active=True,
        password_set=False,
        invite_token_hash=token_hash,
        invite_expires_at=expires_at,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"user": _user_dict(user), "magic_link": _magic_link(token)}


@router.post("/{user_id}/regenerate-invite")
async def regenerate_invite(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.password_set:
        raise HTTPException(status_code=400, detail="User has already set their password")

    token, token_hash = generate_invite_token()
    user.invite_token_hash = token_hash
    user.invite_expires_at = datetime.utcnow() + timedelta(hours=INVITE_EXPIRY_HOURS)
    await db.commit()
    await db.refresh(user)

    return {"user": _user_dict(user), "magic_link": _magic_link(token)}


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    body: UpdateUserBody,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None:
        try:
            user.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid role: {body.role}")

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _token: dict = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_root:
        raise HTTPException(status_code=400, detail="Cannot delete the root user")
    await db.delete(user)
    await db.commit()
