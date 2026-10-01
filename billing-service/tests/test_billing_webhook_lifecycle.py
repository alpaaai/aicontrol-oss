from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.main import app
from app.models import BillingCustomer, ProcessedStripeEvent
from app.services.trial_expiry import TrialExpiry

_client_ctx = TestClient(app)
client = _client_ctx.__enter__()

# See tests/test_billing_webhook.py for why this must be stopped
# immediately after entering the client.
_client_ctx.portal.call(app.state.trial_expiry.stop)

_verify_engine = create_async_engine(settings.database_url, poolclass=NullPool)
_VerifySession = async_sessionmaker(_verify_engine, expire_on_commit=False)


@pytest_asyncio.fixture(loop_scope="session")
async def db_session():
    async with _VerifySession() as session:
        yield session


@pytest.fixture(scope="module", autouse=True)
def _close_client_portal():
    yield
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


async def _seed_customer(db_session, stripe_customer_id: str, status: str = "active") -> None:
    db_session.add(
        BillingCustomer(
            stripe_customer_id=stripe_customer_id,
            email="lifecycle@example.com",
            plan="business",
            subscription_status=status,
            activation_code_hash=f"hash_for_{stripe_customer_id}",
        )
    )
    await db_session.commit()


def _event(event_id: str, event_type: str, stripe_customer_id: str) -> dict:
    return {
        "id": event_id,
        "type": event_type,
        "data": {"object": {"customer": stripe_customer_id}},
    }


def _checkout_completed_event(event_id: str, stripe_customer_id: str, plan: str) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": stripe_customer_id,
                "customer_email": "upgrade-lifecycle@example.com",
                "metadata": {"plan": plan},
            }
        },
    }


class _NoCloseSessionCtx:
    """Wraps an already-open AsyncSession as a context manager that skips
    closing it on exit, so TrialExpiry.run_once() can reuse this test's own
    db_session fixture instead of opening a second pooled connection."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def test_upgrade_from_trial_completes_into_same_row(db_session):
    event_id = "evt_test_upgrade_from_trial"
    stripe_customer_id = "cus_test_upgrade_from_trial"
    await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)

    db_session.add(
        BillingCustomer(
            stripe_customer_id=stripe_customer_id,
            email="upgrade-lifecycle@example.com",
            plan="trial",
            subscription_status="active",
            activation_code_hash=f"hash_for_{stripe_customer_id}",
            trial_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    await db_session.commit()

    try:
        with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = _checkout_completed_event(
                event_id, stripe_customer_id, "business"
            )
            response = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            assert response.status_code == 200

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        customer = rows[0]
        assert customer.plan == "business"
        assert customer.subscription_status == "active"

        expiry = TrialExpiry(session_factory=lambda: _NoCloseSessionCtx(db_session))
        await expiry.run_once()

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        customer = result.scalar_one()
        assert customer.plan == "business"
        assert customer.subscription_status == "active"
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)


@pytest.mark.parametrize(
    "event_type,expected_status",
    [
        ("invoice.paid", "active"),
        ("invoice.payment_failed", "past_due"),
        ("customer.subscription.deleted", "canceled"),
    ],
)
async def test_lifecycle_event_updates_status(db_session, event_type, expected_status):
    event_id = f"evt_test_{event_type.replace('.', '_')}"
    stripe_customer_id = f"cus_test_{event_type.replace('.', '_')}"
    await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)
    await _seed_customer(db_session, stripe_customer_id, status="pending")

    try:
        with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = _event(event_id, event_type, stripe_customer_id)
            response = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            assert response.status_code == 200

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        )
        customer = result.scalar_one()
        assert customer.subscription_status == expected_status
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)


async def test_lifecycle_event_unknown_customer_does_not_500(db_session):
    event_id = "evt_test_unknown_customer"
    stripe_customer_id = "cus_test_does_not_exist"
    await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)

    try:
        with patch("app.routers.billing.stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = _event(event_id, "invoice.paid", stripe_customer_id)
            response = client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"}
            )
            assert response.status_code == 200
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id=stripe_customer_id, event_id=event_id)
