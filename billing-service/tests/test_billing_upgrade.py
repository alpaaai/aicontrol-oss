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


async def _seed_customer(
    db_session, stripe_customer_id: str, code_hash: str, plan: str = "trial"
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
            email="upgrade@example.com",
            plan=plan,
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


async def test_upgrade_happy_path_trial_to_business(db_session):
    stripe_customer_id = "cus_test_upgrade_1"
    code, code_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, code_hash, plan="trial")
    _reset()

    try:
        with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
            mock_create.return_value = "https://checkout.stripe.com/session_upgrade"
            response = client.post(
                "/billing/upgrade",
                json={"activation_code": code, "plan": "business"},
            )
            assert response.status_code == 200
            assert response.json() == {"url": "https://checkout.stripe.com/session_upgrade"}
            mock_create.assert_called_once_with(
                plan="business",
                email="upgrade@example.com",
                existing_customer_id=stripe_customer_id,
            )
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


async def test_upgrade_invalid_activation_code_returns_401(db_session):
    stripe_customer_id = "cus_test_upgrade_2"
    _, code_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, code_hash, plan="trial")
    _reset()

    try:
        with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
            response = client.post(
                "/billing/upgrade",
                json={"activation_code": "not-the-right-code", "plan": "business"},
            )
            assert response.status_code == 401
            mock_create.assert_not_called()
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


async def test_upgrade_non_trial_customer_returns_400(db_session):
    stripe_customer_id = "cus_test_upgrade_3"
    code, code_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, code_hash, plan="business")
    _reset()

    try:
        with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
            response = client.post(
                "/billing/upgrade",
                json={"activation_code": code, "plan": "enterprise"},
            )
            assert response.status_code == 400
            mock_create.assert_not_called()
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


@pytest.mark.parametrize("target_plan", ["trial", "not-a-plan"])
async def test_upgrade_invalid_target_plan_returns_400(db_session, target_plan):
    stripe_customer_id = "cus_test_upgrade_4"
    code, code_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, code_hash, plan="trial")
    _reset()

    try:
        with patch("app.routers.billing.stripe_client.create_checkout_session") as mock_create:
            response = client.post(
                "/billing/upgrade",
                json={"activation_code": code, "plan": target_plan},
            )
            assert response.status_code == 400
            mock_create.assert_not_called()
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


def test_upgrade_rate_limited_after_five_attempts():
    _reset()
    with patch("app.routers.billing.stripe_client.create_checkout_session"):
        for _ in range(5):
            response = client.post(
                "/billing/upgrade", json={"activation_code": "bogus", "plan": "business"}
            )
            assert response.status_code == 401

        response = client.post(
            "/billing/upgrade", json={"activation_code": "bogus", "plan": "business"}
        )
        assert response.status_code == 429
