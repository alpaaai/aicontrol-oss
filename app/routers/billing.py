from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_human
from app.core import license_gate as _lg
from app.models.schemas import AuditEvent
from app.models.database import get_db

router = APIRouter(prefix="/billing", tags=["billing"])

PLAN_CONFIG = {
    "community": {
        "monthly_base_usd": 0.0,
        "rate_per_million": 0.0,
        "retention_days": 7,
        "features": [
            "OPA policy enforcement",
            "Per-agent approved tools enforcement",
            "Rate-based policies",
            "Audit log (7-day retention)",
            "React dashboard — basic views",
            "HITL review queue via API",
            "Unlimited agents",
            "Unlimited policies",
        ],
    },
    "business": {
        "monthly_base_usd": 49.0,
        "rate_per_million": 15.0,
        "retention_days": None,
        "features": [
            "Everything in Community",
            "1-year audit log retention",
            "Slack HITL notifications",
            "HITL review queue dashboard view",
            "Priority email support",
        ],
    },
    "enterprise": {
        "monthly_base_usd": 149.0,
        "rate_per_million": 25.25,
        "retention_days": None,
        "features": [
            "Everything in Business",
            "OPA health-watch observability",
            "Policy drift detection + warning feed",
            "Compliance report export (SOC 2, PCI, HIPAA, GLBA)",
            "SLA (99.9% uptime guarantee)",
        ],
    },
}


async def count_intercepts_in_period(
    db: AsyncSession,
    date_from: datetime,
    date_to: datetime,
) -> int:
    """COUNT(*) audit_events between two timestamps."""
    result = await db.execute(
        select(func.count()).where(
            and_(
                AuditEvent.created_at >= date_from,
                AuditEvent.created_at < date_to,
            )
        )
    )
    return result.scalar() or 0


def _estimate_cost(intercepts: int, rate_per_million: float) -> float:
    return round((intercepts / 1_000_000) * rate_per_million, 2)


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    # DB stores naive UTC timestamps — pass naive datetimes to match column type
    start = datetime(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    end = datetime(year, month, last_day, 23, 59, 59)
    return start, end


def _previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


@router.get("/usage")
async def billing_usage(
    _user=Depends(require_human),
    db: AsyncSession = Depends(get_db),
):
    info = _lg.get_license_info()
    config = PLAN_CONFIG[info.plan]

    now = datetime.utcnow()
    this_year, this_month = now.year, now.month
    prev_year, prev_month = _previous_month(this_year, this_month)

    this_start, this_end = _month_bounds(this_year, this_month)
    prev_start, prev_end = _month_bounds(prev_year, prev_month)

    this_count = await count_intercepts_in_period(db, this_start, this_end)
    prev_count = await count_intercepts_in_period(db, prev_start, prev_end)

    rate = config["rate_per_million"]

    return {
        "plan": info.plan,
        "company": info.company,
        "monthly_base_usd": config["monthly_base_usd"],
        "rate_per_million": rate,
        "retention_days": config["retention_days"],
        "features": config["features"],
        "this_month": {
            "period": f"{this_year}-{this_month:02d}",
            "intercepts": this_count,
            "estimated_cost_usd": _estimate_cost(this_count, rate),
        },
        "last_month": {
            "period": f"{prev_year}-{prev_month:02d}",
            "intercepts": prev_count,
            "estimated_cost_usd": _estimate_cost(prev_count, rate),
        },
        "manage_subscription_url": None,
        "upgrade_url": None,
    }
