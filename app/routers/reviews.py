"""GET /reviews and GET /reviews/{review_id} — human-in-the-loop review status endpoints."""
from typing import Literal, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import _get_verified_token, require_admin, require_human
from app.models.database import async_session_factory, get_db
from app.models.schemas import HITLReview

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewResponse(BaseModel):
    id: UUID
    audit_event_id: Optional[UUID]
    session_id: Optional[UUID]
    status: str
    reviewer: Optional[str]
    review_note: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: UUID,
    token: dict = Depends(_get_verified_token),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    Get review status by ID.
    - Agent tokens: can access any review by ID (UUID provides obscurity).
    - Admin tokens: unrestricted.
    """
    result = await db.execute(
        select(HITLReview).where(HITLReview.id == review_id)
    )
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return review


@router.get("", response_model=list[ReviewResponse])
async def list_reviews(
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, denied"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    token: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewResponse]:
    """
    List reviews. Admin only.
    Optionally filter by status. Ordered by created_at desc.
    """
    query = (
        select(HITLReview)
        .order_by(HITLReview.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if status:
        query = query.where(HITLReview.status == status)

    result = await db.execute(query)
    return result.scalars().all()


class ReviewActionBody(BaseModel):
    action: Literal["approve", "deny"]
    note: Optional[str] = None


@router.patch("/{review_id}")
async def action_review(
    review_id: UUID,
    body: ReviewActionBody,
    _=Depends(require_human),
):
    async with async_session_factory() as session:
        review = (await session.execute(
            select(HITLReview).where(HITLReview.id == review_id)
        )).scalar_one_or_none()
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        review.status = "approved" if body.action == "approve" else "denied"
        review.review_note = body.note
        review.reviewed_at = datetime.utcnow()
        review.reviewer = "dashboard"
        await session.commit()
        await session.refresh(review)
    return {
        "id": str(review.id),
        "status": review.status,
        "review_note": review.review_note,
        "reviewed_at": review.reviewed_at.isoformat(),
    }
