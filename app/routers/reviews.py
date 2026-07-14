"""GET /reviews and GET /reviews/{review_id} — human-in-the-loop review status endpoints."""
from typing import Literal, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Text, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import _get_verified_token, require_human
from app.core.license_gate import require_enterprise_license
from app.models.database import async_session_factory, get_db
from app.models.schemas import AuditEvent as AuditEventModel, HITLReview

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    audit_event_id: Optional[UUID]
    session_id: Optional[UUID]
    status: str
    reviewer: Optional[str]
    review_note: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime
    response_deadline: Optional[datetime] = None
    assigned_to: Optional[str] = None
    tool_name: Optional[str] = None
    tool_parameters: Optional[str] = None


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
    token: dict = Depends(require_human),
    _license=Depends(require_enterprise_license),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewResponse]:
    """
    List reviews. Requires a human JWT (matches PATCH /reviews/{id}) and an
    Enterprise license.
    Optionally filter by status. Ordered by created_at desc.
    """
    q = (
        select(
            HITLReview,
            AuditEventModel.tool_name.label("ae_tool_name"),
            cast(AuditEventModel.tool_parameters, Text).label("ae_tool_params"),
        )
        .outerjoin(AuditEventModel, HITLReview.audit_event_id == AuditEventModel.id)
        .order_by(HITLReview.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if status:
        q = q.where(HITLReview.status == status)

    rows = (await db.execute(q)).all()
    return [
        ReviewResponse(
            id=r.HITLReview.id,
            audit_event_id=r.HITLReview.audit_event_id,
            session_id=r.HITLReview.session_id,
            status=r.HITLReview.status,
            reviewer=r.HITLReview.reviewer,
            review_note=r.HITLReview.review_note,
            reviewed_at=r.HITLReview.reviewed_at,
            created_at=r.HITLReview.created_at,
            response_deadline=r.HITLReview.response_deadline,
            assigned_to=r.HITLReview.assigned_to,
            tool_name=r.ae_tool_name,
            tool_parameters=r.ae_tool_params,
        )
        for r in rows
    ]


class ReviewActionBody(BaseModel):
    action: Literal["approve", "deny"]
    note: Optional[str] = None


@router.patch("/{review_id}")
async def action_review(
    review_id: UUID,
    body: ReviewActionBody,
    _=Depends(require_human),
    _license=Depends(require_enterprise_license),
):
    async with async_session_factory() as session:
        review = (await session.execute(
            select(HITLReview).where(HITLReview.id == review_id)
        )).scalar_one_or_none()
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        if review.status != "pending":
            raise HTTPException(status_code=409, detail="Review already resolved")
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
