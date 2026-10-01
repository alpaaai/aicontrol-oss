from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_human
from app.core import license_gate as _lg
from app.core.logging import get_logger
from app.models.schemas import AuditEvent
from app.models.database import get_db
from app.models.user import OrgSettings
from app.services.billing_client import BillingClientError, fetch_billing_urls

logger = get_logger("billing")

router = APIRouter(prefix="/billing", tags=["billing"])

PLAN_CONFIG = {
    "community": {
        "annual_price_usd": 0.0,
        "retention_days": 7,
        "features": [
            "Cedar policy enforcement",
            "Per-agent approved tools enforcement",
            "Rate-based policies",
            "React dashboard — basic views",
            "HITL review queue via API",
            "Unlimited agents",
            "Unlimited policies",
        ],
    },
    "business": {
        "annual_price_usd": 999.0,
        "retention_days": 30,
        "features": [
            "Slack HITL notifications",
            "HITL review queue dashboard view",
        ],
    },
    "enterprise": {
        "annual_price_usd": 1999.0,
        "retention_days": 90,
        "features": [
            "Policy engine observability",
            "Policy drift detection + warning feed",
            "Compliance report export (SOC 2, EU AI Act, NIST AI RMF, ISO 42001)",
        ],
    },
}
PLAN_CONFIG["trial"] = {
    "annual_price_usd": 0.0,
    "retention_days": 90,
    "features": PLAN_CONFIG["enterprise"]["features"],
}

# Each tier's PLAN_CONFIG["features"] list is additive-only (no "Everything in
# X" placeholder) -- the billing card itemizes every feature the caller's plan
# includes by concatenating every tier up to and including their own.
# "trial" is not in TIER_ORDER: it isn't a fourth cascaded tier, it grants the
# same access as enterprise (see _cascaded_features), and adding it here would
# double-cascade business+enterprise features under a separate trial entry.
TIER_ORDER = ["community", "business", "enterprise"]


def _cascaded_features(plan: str) -> list[str]:
    if plan == "trial":
        return PLAN_CONFIG["enterprise"]["features"]
    features: list[str] = []
    for tier in TIER_ORDER[: TIER_ORDER.index(plan) + 1]:
        features.extend(PLAN_CONFIG[tier]["features"])
    return features


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
    info = await _lg.get_license_info(db)
    config = PLAN_CONFIG[info.plan]

    now = datetime.utcnow()
    this_year, this_month = now.year, now.month
    prev_year, prev_month = _previous_month(this_year, this_month)

    this_start, this_end = _month_bounds(this_year, this_month)
    prev_start, prev_end = _month_bounds(prev_year, prev_month)

    this_count = await count_intercepts_in_period(db, this_start, this_end)
    prev_count = await count_intercepts_in_period(db, prev_start, prev_end)

    activation_code, license_synced_at = (
        await db.execute(select(OrgSettings.activation_code, OrgSettings.license_synced_at).limit(1))
    ).first() or (None, None)

    manage_subscription_url = None
    upgrade_url = None
    if activation_code:
        try:
            urls = await fetch_billing_urls(activation_code, info.plan)
            manage_subscription_url = urls["manage_subscription_url"]
            upgrade_url = urls["upgrade_url"]
        except BillingClientError as exc:
            logger.warning("billing_client_fetch_urls_failed", error=str(exc))

    return {
        "plan": info.plan,
        "company": info.company,
        "annual_price_usd": config["annual_price_usd"],
        "retention_days": config["retention_days"],
        "features": _cascaded_features(info.plan),
        "this_month": {
            "period": f"{this_year}-{this_month:02d}",
            "intercepts": this_count,
        },
        "last_month": {
            "period": f"{prev_year}-{prev_month:02d}",
            "intercepts": prev_count,
        },
        "manage_subscription_url": manage_subscription_url,
        "upgrade_url": upgrade_url,
        "license_status": info.license_status,
        "license_synced_at": license_synced_at.isoformat() if license_synced_at else None,
    }
