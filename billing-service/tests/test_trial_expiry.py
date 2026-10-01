import uuid
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import select

from app.models import BillingCustomer
from app.services.trial_expiry import TrialExpiry


@pytest_asyncio.fixture(loop_scope="session")
async def db_session():
    from app.database import async_session_factory

    async with async_session_factory() as session:
        yield session


class _NoCloseSessionCtx:
    """Wraps an already-open AsyncSession as a context manager that skips
    closing it on exit, so tests can keep using the same session/fixture
    after TrialExpiry.run_once() finishes its own `async with` block."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def _make_customer(db_session, **overrides):
    defaults = dict(
        id=uuid.uuid4(),
        stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
        email="trial-expiry-test@example.com",
        plan="trial",
        subscription_status="active",
        activation_code_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        trial_expires_at=None,
    )
    defaults.update(overrides)
    customer = BillingCustomer(**defaults)
    db_session.add(customer)
    await db_session.commit()
    return customer


async def test_run_once_reverts_expired_trial(db_session):
    customer = await _make_customer(
        db_session,
        trial_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    try:
        expiry = TrialExpiry(session_factory=lambda: _NoCloseSessionCtx(db_session))
        await expiry.run_once()

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.id == customer.id)
        )
        fetched = result.scalar_one()
        assert fetched.plan == "community"
        assert fetched.subscription_status == "expired"
    finally:
        await db_session.delete(customer)
        await db_session.commit()


async def test_run_once_leaves_future_trial_untouched(db_session):
    customer = await _make_customer(
        db_session,
        trial_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    try:
        expiry = TrialExpiry(session_factory=lambda: _NoCloseSessionCtx(db_session))
        await expiry.run_once()

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.id == customer.id)
        )
        fetched = result.scalar_one()
        assert fetched.plan == "trial"
        assert fetched.subscription_status == "active"
    finally:
        await db_session.delete(customer)
        await db_session.commit()


async def test_run_once_leaves_non_trial_plan_untouched(db_session):
    customer = await _make_customer(
        db_session,
        plan="business",
        subscription_status="active",
        trial_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    try:
        expiry = TrialExpiry(session_factory=lambda: _NoCloseSessionCtx(db_session))
        await expiry.run_once()

        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.id == customer.id)
        )
        fetched = result.scalar_one()
        assert fetched.plan == "business"
        assert fetched.subscription_status == "active"
    finally:
        await db_session.delete(customer)
        await db_session.commit()
