import hashlib
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limiter import check_rate_limit, client_ip
from app.database import get_db
from app.models import BillingCustomer, ProcessedStripeEvent
from app.services import email_client, stripe_client
from app.services.activation_code import generate_activation_code, verify_activation_code

logger = get_logger("billing")

router = APIRouter()

_LIFECYCLE_EVENT_STATUS = {
    "invoice.paid": "active",
    "invoice.payment_failed": "past_due",
    "customer.subscription.deleted": "canceled",
}


class CheckoutRequest(BaseModel):
    plan: str
    email: str | None = None


@router.post("/billing/checkout")
async def checkout(payload: CheckoutRequest, request: Request) -> dict:
    check_rate_limit(f"checkout:ip:{client_ip(request)}", max_attempts=5, window_seconds=600)
    try:
        url = stripe_client.create_checkout_session(plan=payload.plan, email=payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except stripe.error.StripeError:
        logger.warning("stripe_checkout_session_failed", plan=payload.plan)
        raise HTTPException(status_code=502, detail="payment provider error, please try again")
    return {"url": url}


class PortalRequest(BaseModel):
    activation_code: str


class UpgradeRequest(BaseModel):
    activation_code: str
    plan: str


async def _lookup_customer_by_activation_code(
    db: AsyncSession, code: str
) -> BillingCustomer | None:
    """Look up the customer by hashing the supplied code (the hash column is
    unique and unsalted, so an exact-match query is equivalent to hashing
    every row and comparing). Confirms with verify_activation_code() so the
    module that owns activation-code semantics is the one doing the check."""
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    result = await db.execute(
        select(BillingCustomer).where(BillingCustomer.activation_code_hash == code_hash)
    )
    customer = result.scalar_one_or_none()
    if customer is None or not verify_activation_code(code, customer.activation_code_hash):
        return None
    return customer


@router.post("/billing/portal")
async def portal(
    payload: PortalRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    check_rate_limit(f"portal:ip:{client_ip(request)}", max_attempts=5, window_seconds=600)
    customer = await _lookup_customer_by_activation_code(db, payload.activation_code)
    if customer is None:
        raise HTTPException(status_code=401, detail="invalid activation code")
    url = stripe_client.create_portal_session(stripe_customer_id=customer.stripe_customer_id)
    return {"url": url}


@router.post("/billing/upgrade")
async def upgrade(
    payload: UpgradeRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    """Mid-trial upgrade: trial customer -> business/enterprise, reusing the
    trial's existing Stripe Customer so the checkout completion updates the
    same billing_customers row instead of creating a duplicate."""
    check_rate_limit(f"upgrade:ip:{client_ip(request)}", max_attempts=5, window_seconds=600)
    customer = await _lookup_customer_by_activation_code(db, payload.activation_code)
    if customer is None:
        raise HTTPException(status_code=401, detail="invalid activation code")
    if customer.plan != "trial":
        raise HTTPException(status_code=400, detail="only trial customers can upgrade here")
    if payload.plan not in ("business", "enterprise"):
        raise HTTPException(status_code=400, detail=f"invalid upgrade plan: {payload.plan}")
    url = stripe_client.create_checkout_session(
        plan=payload.plan,
        email=customer.email,
        existing_customer_id=customer.stripe_customer_id,
    )
    return {"url": url}


class ReissueActivationRequest(BaseModel):
    email: str
    stripe_customer_id: str


@router.post("/billing/reissue-activation")
async def reissue_activation(
    payload: ReissueActivationRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    """Lost/leaked activation code recovery. Authenticates on {email,
    stripe_customer_id} together -- not email alone, which isn't guaranteed
    unique enough across Stripe test/live or repeat checkouts."""
    check_rate_limit(f"reissue:ip:{client_ip(request)}", max_attempts=5, window_seconds=600)
    result = await db.execute(
        select(BillingCustomer).where(
            BillingCustomer.email == payload.email,
            BillingCustomer.stripe_customer_id == payload.stripe_customer_id,
        )
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="no matching subscription found")

    activation_code, code_hash = generate_activation_code()
    customer.activation_code_hash = code_hash
    email_client.send_activation_email(to=customer.email, activation_code=activation_code)
    return {"status": "reissued"}


async def _mark_event_processed(db: AsyncSession, event_id: str) -> bool:
    """Insert event_id into processed_stripe_events if not already there.

    Returns True if this is a new event (side effect should run), False if
    it's a duplicate delivery (already processed).
    """
    stmt = (
        pg_insert(ProcessedStripeEvent)
        .values(event_id=event_id)
        .on_conflict_do_nothing(index_elements=["event_id"])
    )
    result = await db.execute(stmt)
    return result.rowcount > 0


async def _handle_checkout_session_completed(db: AsyncSession, session_obj: dict) -> None:
    stripe_customer_id = session_obj["customer"]
    email = (session_obj.get("customer_details") or {}).get("email") or session_obj.get(
        "customer_email"
    )
    plan = (session_obj.get("metadata") or {}).get("plan")
    subscription_id = session_obj.get("subscription")

    result = await db.execute(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    )
    customer = result.scalar_one_or_none()
    activation_code, code_hash = generate_activation_code()
    trial_expires_at = (
        datetime.now(timezone.utc) + timedelta(days=90) if plan == "trial" else None
    )

    if customer is None:
        db.add(
            BillingCustomer(
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=subscription_id,
                email=email,
                plan=plan,
                subscription_status="active",
                activation_code_hash=code_hash,
                trial_expires_at=trial_expires_at,
            )
        )
    else:
        customer.stripe_subscription_id = subscription_id
        customer.email = email
        customer.plan = plan
        customer.subscription_status = "active"
        customer.activation_code_hash = code_hash
        customer.trial_expires_at = trial_expires_at

    email_client.send_activation_email(to=email, activation_code=activation_code)


@router.get("/license/sync")
async def license_sync(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Activation-code-authenticated status check. No JWT issuance -- the
    response itself is the entitlement signal (outline doc step 5)."""
    check_rate_limit(f"sync:ip:{client_ip(request)}", max_attempts=20, window_seconds=3600)
    auth_header = request.headers.get("authorization", "")
    code = auth_header[7:] if auth_header.lower().startswith("bearer ") else auth_header
    customer = await _lookup_customer_by_activation_code(db, code) if code else None
    if customer is None:
        raise HTTPException(status_code=401, detail="invalid activation code")
    return {"status": customer.subscription_status, "plan": customer.plan}


async def _handle_subscription_status_change(
    db: AsyncSession, stripe_customer_id: str, new_status: str
) -> None:
    result = await db.execute(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        logger.warning(
            "billing_customer_not_found_for_lifecycle_event",
            stripe_customer_id=stripe_customer_id,
            new_status=new_status,
        )
        return
    customer.subscription_status = new_status


@router.post("/billing/webhook")
async def webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="missing stripe-signature header")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=401, detail="invalid signature")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid payload")

    is_new = await _mark_event_processed(db, event["id"])
    if is_new:
        event_type = event["type"]
        obj = event["data"]["object"]
        if event_type == "checkout.session.completed":
            await _handle_checkout_session_completed(db, obj)
        elif event_type in _LIFECYCLE_EVENT_STATUS:
            await _handle_subscription_status_change(
                db, obj["customer"], _LIFECYCLE_EVENT_STATUS[event_type]
            )

    return {"received": True}
