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


async def _seed_customer(db_session, stripe_customer_id: str, code_hash: str) -> None:
    result = await db_session.execute(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    )
    for row in result.scalars().all():
        await db_session.delete(row)
    await db_session.commit()

    db_session.add(
        BillingCustomer(
            stripe_customer_id=stripe_customer_id,
            email="portal@example.com",
            plan="business",
            subscription_status="active",
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


async def test_portal_valid_code_returns_url(db_session):
    stripe_customer_id = "cus_test_portal_1"
    code, code_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, code_hash)
    _reset()

    try:
        with patch("app.routers.billing.stripe_client.create_portal_session") as mock_create:
            mock_create.return_value = "https://billing.stripe.com/session_abc"
            response = client.post("/billing/portal", json={"activation_code": code})
            assert response.status_code == 200
            assert response.json() == {"url": "https://billing.stripe.com/session_abc"}
            mock_create.assert_called_once_with(stripe_customer_id=stripe_customer_id)
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


async def test_portal_invalid_code_returns_401(db_session):
    stripe_customer_id = "cus_test_portal_2"
    _, code_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, code_hash)
    _reset()

    try:
        with patch("app.routers.billing.stripe_client.create_portal_session") as mock_create:
            response = client.post("/billing/portal", json={"activation_code": "not-the-right-code"})
            assert response.status_code == 401
            mock_create.assert_not_called()
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


def test_portal_rate_limited_after_five_attempts():
    _reset()
    with patch("app.routers.billing.stripe_client.create_portal_session"):
        for _ in range(5):
            response = client.post("/billing/portal", json={"activation_code": "bogus"})
            assert response.status_code == 401

        response = client.post("/billing/portal", json={"activation_code": "bogus"})
        assert response.status_code == 429
