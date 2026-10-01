import uuid
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import select

from app.models import BillingCustomer, ProcessedStripeEvent


@pytest_asyncio.fixture(loop_scope="session")
async def db_session():
    from app.database import async_session_factory

    async with async_session_factory() as session:
        yield session


async def test_insert_and_read_billing_customer(db_session):
    customer_id = uuid.uuid4()
    customer = BillingCustomer(
        id=customer_id,
        stripe_customer_id="cus_test123",
        stripe_subscription_id="sub_test123",
        email="customer@example.com",
        company="Acme Corp",
        plan="business",
        subscription_status="active",
        activation_code_hash="a" * 64,
    )
    db_session.add(customer)
    await db_session.commit()

    try:
        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.id == customer_id)
        )
        fetched = result.scalar_one()
        assert fetched.stripe_customer_id == "cus_test123"
        assert fetched.email == "customer@example.com"
        assert fetched.plan == "business"
        assert fetched.subscription_status == "active"
        assert fetched.activation_code_hash == "a" * 64
    finally:
        await db_session.delete(customer)
        await db_session.commit()


async def test_insert_and_read_billing_customer_trial_expires_at(db_session):
    customer_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(days=90)
    customer = BillingCustomer(
        id=customer_id,
        stripe_customer_id="cus_trial123",
        email="trial@example.com",
        plan="trial",
        subscription_status="active",
        activation_code_hash="b" * 64,
        trial_expires_at=expires_at,
    )
    db_session.add(customer)
    await db_session.commit()

    try:
        result = await db_session.execute(
            select(BillingCustomer).where(BillingCustomer.id == customer_id)
        )
        fetched = result.scalar_one()
        assert fetched.trial_expires_at is not None
        assert abs((fetched.trial_expires_at.replace(tzinfo=timezone.utc) - expires_at).total_seconds()) < 5
    finally:
        await db_session.delete(customer)
        await db_session.commit()


async def test_insert_and_read_processed_stripe_event(db_session):
    event = ProcessedStripeEvent(event_id="evt_test123")
    db_session.add(event)
    await db_session.commit()

    try:
        result = await db_session.execute(
            select(ProcessedStripeEvent).where(ProcessedStripeEvent.event_id == "evt_test123")
        )
        fetched = result.scalar_one()
        assert fetched.event_id == "evt_test123"
        assert fetched.processed_at is not None
    finally:
        await db_session.delete(event)
        await db_session.commit()
