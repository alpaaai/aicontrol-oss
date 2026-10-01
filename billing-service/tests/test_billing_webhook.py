from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
import stripe
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.main import app
from app.models import BillingCustomer, ProcessedStripeEvent

# Entering TestClient as a context manager keeps one portal (one event
# loop) alive across every request made through `client`. Without this,
# each client.post() opens and tears down its own portal/loop, and
# app.database's pooled asyncpg connections (bound to whichever loop first
# used them) then get reused from a second, different loop on the next
# call -- "attached to a different loop" / "Event loop is closed".
_client_ctx = TestClient(app)
client = _client_ctx.__enter__()

# Entering the client above runs the real app lifespan, which starts a
# real TrialExpiry background task (app/main.py, plans/v4 trial-refund-
# pricing task 10) on this portal's loop. Left running, its 5-second
# stabilization sleep fires mid-module and its DB query races the shared
# app.database.engine pool against other test files' own ad-hoc portals,
# corrupting pooled connections ("attached to a different loop" in
# unrelated test modules). This module doesn't exercise TrialExpiry --
# stop it immediately, before its timer can ever fire.
_client_ctx.portal.call(app.state.trial_expiry.stop)

# TestClient runs the app in its own event loop (a separate thread/portal
# from pytest-asyncio's session loop this file's async tests run in).
# app.database's module-level engine is bound to whichever loop touches it
# first, so verification queries here use a dedicated NullPool engine
# instead of sharing that pool across loops (asyncpg connections are
# loop-bound; sharing them cross-loop raises "attached to a different loop").
_verify_engine = create_async_engine(settings.database_url, poolclass=NullPool)
_VerifySession = async_sessionmaker(_verify_engine, expire_on_commit=False)


@pytest_asyncio.fixture(loop_scope="session")
async def db_session():
    async with _VerifySession() as session:
        yield session


@pytest.fixture(scope="module", autouse=True)
def _close_client_portal():
    yield
    # app.database.engine's asyncpg connections were opened inside this
    # TestClient's portal loop (see comment above). Dispose them from that
    # same loop before tearing the portal down, so other test modules that
    # touch app.database.engine from pytest-asyncio's own loop (e.g.
    # test_models.py) rebind it fresh instead of hitting a stale
    # loop-bound connection.
    from app.database import engine

    _client_ctx.portal.call(engine.dispose)
    _client_ctx.__exit__(None, None, None)


async def _cleanup(db_session, stripe_customer_id=None, event_id=None):
    if stripe_customer_id:
        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        for row in result.scalars().all():
            await db_session.delete(row)
    if event_id:
        result = await db_session.execute(
            select(ProcessedStripeEvent).where(ProcessedStripeEvent.event_id == event_id)
        )
        for row in result.scalars().all():
            await db_session.delete(row)
    await db_session.commit()


def _checkout_completed_event(
    event_id: str, stripe_customer_id: str, plan: str = "business"
) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": stripe_customer_id,
                "subscription": "sub_test123",
                "customer_details": {"email": "customer@example.com"},
                "metadata": {"plan": plan},
            }
        },
    }


def test_webhook_missing_signature_rejected():
    response = client.post("/billing/webhook", content=b"{}")
    assert response.status_code == 400


def test_webhook_bad_signature_rejected():
    with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct:
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "bad signature", "sig_header"
        )
        response = client.post(
            "/billing/webhook", content=b"{}", headers={"stripe-signature": "bad"}
        )
        assert response.status_code == 401


async def test_webhook_checkout_completed_creates_row_and_activation_code(db_session):
    event_id = "evt_test_completed_1"
    stripe_customer_id = "cus_test_completed_1"
    await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)

    try:
        with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct, patch(
            "app.routers.billing.email_client.send_activation_email"
        ) as mock_send_email:
            mock_construct.return_value = _checkout_completed_event(event_id, stripe_customer_id)
            response = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            assert response.status_code == 200
            assert mock_send_email.call_count == 1
            assert mock_send_email.call_args.kwargs["to"] == "customer@example.com"
            assert mock_send_email.call_args.kwargs["activation_code"]

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        customer = result.scalar_one()
        assert customer.email == "customer@example.com"
        assert customer.plan == "business"
        assert customer.subscription_status == "active"
        assert customer.activation_code_hash

        result = await db_session.execute(
            select(ProcessedStripeEvent).where(ProcessedStripeEvent.event_id == event_id)
        )
        assert result.scalar_one() is not None
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)


async def test_webhook_checkout_completed_trial_sets_trial_expires_at(db_session):
    event_id = "evt_test_trial_1"
    stripe_customer_id = "cus_test_trial_1"
    await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)

    try:
        with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct, patch(
            "app.routers.billing.email_client.send_activation_email"
        ):
            mock_construct.return_value = _checkout_completed_event(
                event_id, stripe_customer_id, plan="trial"
            )
            response = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            assert response.status_code == 200

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        customer = result.scalar_one()
        assert customer.plan == "trial"
        assert customer.trial_expires_at is not None
        expected = datetime.now(timezone.utc) + timedelta(days=90)
        actual = customer.trial_expires_at
        if actual.tzinfo is None:
            actual = actual.replace(tzinfo=timezone.utc)
        assert abs((actual - expected).total_seconds()) < 10
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)


async def test_webhook_checkout_completed_non_trial_leaves_trial_expires_at_none(db_session):
    event_id = "evt_test_nontrial_1"
    stripe_customer_id = "cus_test_nontrial_1"
    await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)

    try:
        with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct, patch(
            "app.routers.billing.email_client.send_activation_email"
        ):
            mock_construct.return_value = _checkout_completed_event(
                event_id, stripe_customer_id, plan="business"
            )
            response = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            assert response.status_code == 200

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        customer = result.scalar_one()
        assert customer.plan == "business"
        assert customer.trial_expires_at is None
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)


async def test_webhook_checkout_completed_row_survives_email_send_failure(db_session):
    event_id = "evt_test_email_fails_1"
    stripe_customer_id = "cus_test_email_fails_1"
    await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)

    try:
        with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct, patch(
            "app.services.email_client.httpx.post"
        ) as mock_post:
            mock_construct.return_value = _checkout_completed_event(event_id, stripe_customer_id)
            mock_post.side_effect = Exception("resend is down")

            response = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            assert response.status_code == 200

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        customer = result.scalar_one()
        assert customer.activation_code_hash
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)


async def test_webhook_checkout_completed_upgrade_clears_trial_expires_at(db_session):
    event_id = "evt_test_upgrade_1"
    stripe_customer_id = "cus_test_upgrade_1"
    await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)

    db_session.add(
        BillingCustomer(
            stripe_customer_id=stripe_customer_id,
            email="customer@example.com",
            plan="trial",
            subscription_status="active",
            activation_code_hash="a" * 64,
            trial_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    await db_session.commit()

    try:
        with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct, patch(
            "app.routers.billing.email_client.send_activation_email"
        ):
            mock_construct.return_value = _checkout_completed_event(
                event_id, stripe_customer_id, plan="business"
            )
            response = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            assert response.status_code == 200

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        customer = result.scalar_one()
        assert customer.plan == "business"
        assert customer.trial_expires_at is None
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)


async def test_webhook_duplicate_event_id_is_idempotent(db_session):
    event_id = "evt_test_dup_1"
    stripe_customer_id = "cus_test_dup_1"
    await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)

    try:
        with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct, patch(
            "app.routers.billing.email_client.send_activation_email"
        ):
            mock_construct.return_value = _checkout_completed_event(event_id, stripe_customer_id)

            first = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            second = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            assert first.status_code == 200
            assert second.status_code == 200

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        assert len(result.scalars().all()) == 1

        result = await db_session.execute(
            select(ProcessedStripeEvent).where(ProcessedStripeEvent.event_id == event_id)
        )
        assert len(result.scalars().all()) == 1
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)
