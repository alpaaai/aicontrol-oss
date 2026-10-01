"""All Stripe SDK calls live here. Everything else mocks this module."""
import stripe

from app.core.config import settings

stripe.api_key = settings.stripe_secret_key
stripe.api_version = "2026-08-26.dahlia"

_SUCCESS_URL = "https://aictl.io/pricing?checkout=success"
_CANCEL_URL = "https://aictl.io/pricing?checkout=cancel"

_PRICE_IDS = {
    "business": settings.stripe_price_id_business,
    "enterprise": settings.stripe_price_id_enterprise,
    "trial": settings.stripe_price_id_trial,
}


def create_checkout_session(
    plan: str, email: str | None = None, existing_customer_id: str | None = None
) -> str:
    """Create a Stripe Checkout session for a plan. Returns its URL.

    When email is omitted, Stripe's own hosted checkout page collects it."""
    if plan not in _PRICE_IDS:
        raise ValueError(f"unknown plan: {plan}")

    kwargs = {
        "mode": "payment" if plan == "trial" else "subscription",
        "line_items": [{"price": _PRICE_IDS[plan], "quantity": 1}],
        "success_url": _SUCCESS_URL,
        "cancel_url": _CANCEL_URL,
        "metadata": {"plan": plan},
    }
    if existing_customer_id is not None:
        kwargs["customer"] = existing_customer_id
    elif email is not None:
        kwargs["customer_email"] = email

    session = stripe.checkout.Session.create(**kwargs)
    return session.url


def create_portal_session(stripe_customer_id: str) -> str:
    """Create a Stripe Billing Portal session for an existing customer. Returns its URL."""
    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=settings.stripe_portal_return_url,
    )
    return session.url
