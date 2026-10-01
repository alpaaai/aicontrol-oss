from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.rate_limiter import reset_rate_limits
from app.main import app
from app.models import BillingCustomer
from app.services.activation_code import generate_activation_code

# See tests/test_billing_webhook.py for why TestClient is entered as a
# context manager here (keeps one portal/event-loop alive across requests
# so app.database's pooled asyncpg connections aren't reused cross-loop).
_client_ctx = TestClient(app)
client = _client_ctx.__enter__()

# Entering the client above starts a real TrialExpiry background task
# (app/main.py) on this portal's loop -- see tests/test_billing_webhook.py
# for why it must be stopped immediately, before its 5s timer can fire and
# race the shared app.database.engine pool against other test modules.
_client_ctx.portal.call(app.state.trial_expiry.stop)

_verify_engine = create_async_engine(settings.database_url, poolclass=NullPool)
_VerifySession = async_sessionmaker(_verify_engine, expire_on_commit=False)


@pytest_asyncio.fixture(loop_scope="session")
async def db_session():
    async with _VerifySession() as session:
        yield session


@pytest.fixture(scope="module", autouse=True)
def _close_client_sync():
    yield
    from app.database import engine

    _client_ctx.portal.call(engine.dispose)
    _client_ctx.__exit__(None, None, None)


async def _seed_customer(
    db_session, stripe_customer_id: str, code_hash: str, status: str = "active", plan: str = "business"
) -> None:
    result = await db_session.execute(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    )
    for row in result.scalars().all():
        await db_session.delete(row)
    await db_session.commit()

    db_session.add(
        BillingCustomer(
            stripe_customer_id=stripe_customer_id,
            email="sync@example.com",
            plan=plan,
            subscription_status=status,
            activation_code_hash=code_hash,
        )
    )
    await db_session.commit()


async def _cleanup(db_session, stripe_customer_id: str) -> None:
    result = await db_session.execute(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    )
    for row in result.scalars().all():
        await db_session.delete(row)
    await db_session.commit()


def _reset():
    reset_rate_limits()


async def test_sync_valid_code_returns_status_and_plan(db_session):
    stripe_customer_id = "cus_test_sync_1"
    code, code_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, code_hash, status="past_due", plan="enterprise")
    _reset()

    try:
        response = client.get("/license/sync", headers={"Authorization": f"Bearer {code}"})
        assert response.status_code == 200
        assert response.json() == {"status": "past_due", "plan": "enterprise"}
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


async def test_sync_invalid_code_returns_401():
    _reset()
    response = client.get("/license/sync", headers={"Authorization": "Bearer not-a-real-code"})
    assert response.status_code == 401


async def test_sync_missing_header_returns_401():
    _reset()
    response = client.get("/license/sync")
    assert response.status_code == 401


async def test_sync_expired_trial_reports_expired_status_and_community_plan(db_session):
    """plans/v4 task 11: a trial row the TrialExpiry job has already reverted
    (plan='community', subscription_status='expired') must report that
    reverted state through /license/sync -- confirms no extra code is
    needed beyond Tasks 7-9."""
    stripe_customer_id = "cus_test_sync_expired_trial"
    code, code_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, code_hash, status="expired", plan="community")
    _reset()

    try:
        response = client.get("/license/sync", headers={"Authorization": f"Bearer {code}"})
        assert response.status_code == 200
        assert response.json() == {"status": "expired", "plan": "community"}
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


def test_sync_rate_limited_after_twenty_attempts():
    _reset()
    for _ in range(20):
        response = client.get("/license/sync", headers={"Authorization": "Bearer bogus"})
        assert response.status_code == 401

    response = client.get("/license/sync", headers={"Authorization": "Bearer bogus"})
    assert response.status_code == 429
