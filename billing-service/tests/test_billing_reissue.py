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
from app.services.activation_code import generate_activation_code, verify_activation_code

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
def _close_client_reissue():
    yield
    from app.database import engine

    _client_ctx.portal.call(engine.dispose)
    _client_ctx.__exit__(None, None, None)


async def _seed_customer(db_session, stripe_customer_id: str, email: str, code_hash: str) -> None:
    result = await db_session.execute(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    )
    for row in result.scalars().all():
        await db_session.delete(row)
    await db_session.commit()

    db_session.add(
        BillingCustomer(
            stripe_customer_id=stripe_customer_id,
            email=email,
            plan="business",
            subscription_status="active",
            activation_code_hash=code_hash,
        )
    )
    await db_session.commit()


async def _get_customer(db_session, stripe_customer_id: str) -> BillingCustomer:
    result = await db_session.execute(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    )
    return result.scalar_one()


async def _cleanup(db_session, stripe_customer_id: str) -> None:
    result = await db_session.execute(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    )
    for row in result.scalars().all():
        await db_session.delete(row)
    await db_session.commit()


def _reset():
    reset_rate_limits()


async def test_reissue_valid_pair_emails_new_code_and_invalidates_old(db_session):
    stripe_customer_id = "cus_test_reissue_1"
    email = "reissue@example.com"
    old_code, old_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, email, old_hash)
    _reset()

    try:
        with patch("app.routers.billing.email_client.send_activation_email") as mock_send:
            response = client.post(
                "/billing/reissue-activation",
                json={"email": email, "stripe_customer_id": stripe_customer_id},
            )
            assert response.status_code == 200
            mock_send.assert_called_once()
            sent_kwargs = mock_send.call_args.kwargs
            assert sent_kwargs["to"] == email
            new_code = sent_kwargs["activation_code"]

        db_session.expire_all()
        customer = await _get_customer(db_session, stripe_customer_id)
        assert not verify_activation_code(old_code, customer.activation_code_hash)
        assert verify_activation_code(new_code, customer.activation_code_hash)

        old_sync = client.get("/license/sync", headers={"Authorization": f"Bearer {old_code}"})
        assert old_sync.status_code == 401
        with patch("app.routers.billing.stripe_client.create_portal_session"):
            old_portal = client.post("/billing/portal", json={"activation_code": old_code})
            assert old_portal.status_code == 401
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


async def test_reissue_mismatched_pair_returns_404(db_session):
    stripe_customer_id = "cus_test_reissue_2"
    email = "reissue2@example.com"
    _, code_hash = generate_activation_code()
    await _seed_customer(db_session, stripe_customer_id, email, code_hash)
    _reset()

    try:
        with patch("app.routers.billing.email_client.send_activation_email") as mock_send:
            response = client.post(
                "/billing/reissue-activation",
                json={"email": email, "stripe_customer_id": "cus_wrong"},
            )
            assert response.status_code == 404
            mock_send.assert_not_called()
    finally:
        await db_session.rollback()
        await _cleanup(db_session, stripe_customer_id)


def test_reissue_rate_limited_after_five_attempts():
    _reset()
    with patch("app.routers.billing.email_client.send_activation_email"):
        for _ in range(5):
            response = client.post(
                "/billing/reissue-activation",
                json={"email": "nobody@example.com", "stripe_customer_id": "cus_bogus"},
            )
            assert response.status_code == 404

        response = client.post(
            "/billing/reissue-activation",
            json={"email": "nobody@example.com", "stripe_customer_id": "cus_bogus"},
        )
        assert response.status_code == 429
